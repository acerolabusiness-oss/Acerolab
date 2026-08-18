"""A fila de produção.

Um trabalhador em segundo plano puxa um vídeo por vez da tabela `videos` e
roda a esteira inteira nele, anotando em que etapa está para a tela poder
mostrar progresso de verdade em vez de uma ampulheta.

Por que um vídeo por vez: gerar imagem e renderizar são pesados, e duas
esteiras concorrendo na mesma máquina terminam as duas mais devagar. Quando
a fila crescer, o caminho é mais máquina, não mais linha aqui.

Regra da casa: **vídeo que falha não some**. Fica com o estado `falhou` e a
mensagem do erro, porque as etapas que rodaram antes já foram cobradas de
nós e precisam aparecer na conta.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import traceback
from pathlib import Path

from esteira import clipes as etapa_clipes
from esteira import direcao as etapa_direcao
from esteira import imagens as etapa_imagens
from esteira import legenda_png as etapa_legenda_png
from esteira import legendas as etapa_legendas
from esteira import narracao as etapa_narracao
from esteira import render as etapa_render
from esteira import roteiro as etapa_roteiro
from esteira.config import SAIDA, Precos, Serie
from esteira.custos import Custos

from . import capas, catalogo, piloto
from .banco import agora, aberto, lista_json, um

PAUSA = 2.0          # segundos entre olhadas na fila quando está vazia
_parar = threading.Event()


# ───────────────────────── montagem da série ─────────────────────────

def montar_serie(linha: sqlite3.Row, video: sqlite3.Row | None = None) -> Serie:
    """Traduz a linha do banco nos parâmetros que a esteira entende."""
    duracao = catalogo.DURACAO_POR_CHAVE.get(linha["duracao"], catalogo.DURACOES[0])
    estilo = catalogo.ESTILO_POR_CHAVE.get(linha["estilo"])
    modo_musica = (video["modo_musica"] if video is not None else linha["modo_musica"])
    return Serie(
        nicho=linha["nicho_texto"],
        idioma=linha["idioma"],
        voz=linha["voz"],
        musica_fundo=(catalogo.sortear_musica(lista_json(linha["musicas"]))
                      if modo_musica == "biblioteca" else None),
        estilo=estilo.prompt if estilo else catalogo.ESTILOS[0].prompt,
        legenda=True,
        modo=linha["modo"],
        modelo_video=linha["modelo_video"],
        cenas=duracao.cenas,
    )


# ──────────────────────────── um vídeo ───────────────────────────────

def _etapa(con: sqlite3.Connection, video_id: int, nome: str) -> None:
    con.execute("UPDATE videos SET etapa = ? WHERE id = ?", (nome, video_id))


def produzir(con: sqlite3.Connection, video: sqlite3.Row) -> None:
    linha_serie = um(con, "SELECT * FROM series WHERE id = ?", video["serie_id"])
    if linha_serie is None:
        raise RuntimeError("a série deste vídeo não existe mais")

    serie = montar_serie(linha_serie, video)
    custos = Custos(precos=Precos())
    pasta = SAIDA / f"video_{video['id']:06d}"
    pasta.mkdir(parents=True, exist_ok=True)

    assunto = None
    if video["tema_id"]:
        tema = um(con, "SELECT titulo, gancho FROM temas WHERE id = ?", video["tema_id"])
        if tema:
            assunto = (f"um vídeo com o título \"{tema['titulo']}\", "
                       f"abrindo a narração com: {tema['gancho']}")

    _etapa(con, video["id"], "roteiro")
    roteiro = etapa_roteiro.gerar(serie, custos, assunto=assunto)
    con.execute("UPDATE videos SET titulo = ? WHERE id = ?",
                (roteiro.titulo, video["id"]))

    _etapa(con, video["id"], "direção visual")
    if serie.modo == "video":
        quadros = etapa_clipes.gerar(
            roteiro, serie, pasta / "cenas", custos, modelo=serie.modelo_video)
    elif serie.modo == "automatico":
        quadros = etapa_imagens.gerar(roteiro, serie, pasta / "cenas", custos)
        indices = etapa_direcao.cenas_com_movimento(roteiro)
        try:
            movimentos = etapa_clipes.gerar(
                roteiro, serie, pasta / "cenas", custos,
                modelo=serie.modelo_video, indices=indices,
                tolerar_falhas=True)
            for caminho in movimentos:
                indice = int(caminho.stem.rsplit("_", 1)[-1])
                quadros[indice] = caminho
        except Exception as erro:                           # noqa: BLE001
            # A automação não perde o vídeo inteiro se a fila de clipes cair:
            # as imagens já prontas viram o fallback visual daquela execução.
            print(f"[fila] clipes do vídeo {video['id']} indisponíveis: {erro}")
    else:
        quadros = etapa_imagens.gerar(roteiro, serie, pasta / "cenas", custos)

    _etapa(con, video["id"], "narração")
    audio, _ = etapa_narracao.gerar(roteiro, serie, pasta / "narracao.mp3", custos)

    _etapa(con, video["id"], "legendas")
    palavras = etapa_legendas.transcrever(audio, serie.idioma, custos)
    estilo_legenda = catalogo.LEGENDA_POR_CHAVE.get(
        linha_serie["legenda"], catalogo.LEGENDAS[0])
    if etapa_render.tem_libass():
        legenda = etapa_legendas.escrever_ass(
            palavras, pasta / "legenda.ass", serie.largura, serie.altura,
            cor=estilo_legenda.cor, contorno=estilo_legenda.contorno,
            caixa_alta=estilo_legenda.caixa_alta,
            divisor_contorno=estilo_legenda.peso_contorno)
    else:
        legenda = etapa_legenda_png.desenhar(
            palavras, pasta / "legenda", serie.largura, serie.altura,
            cor=estilo_legenda.cor, contorno=estilo_legenda.contorno,
            caixa_alta=estilo_legenda.caixa_alta,
            divisor_contorno=estilo_legenda.peso_contorno,
        )

    _etapa(con, video["id"], "montagem")
    (pasta / "midias.json").write_text(
        json.dumps([p.name for p in quadros], ensure_ascii=False, indent=2),
        encoding="utf-8")
    arquivo, segundos_render = etapa_render.montar(
        quadros, audio, legenda, serie, pasta / "video.mp4",
        roteiro=roteiro, palavras=palavras)

    custos.registrar("render", "segundos", segundos_render, 0.0,
                     f"{segundos_render:.1f}s de CPU (custo de servidor, não de API)")

    _etapa(con, video["id"], "capa")
    capas.gerar(arquivo, pasta / "capa.webp")
    custos.salvar(pasta / "custo.json")
    (pasta / "roteiro.json").write_text(
        roteiro.model_dump_json(indent=2), encoding="utf-8")

    con.execute("""
        UPDATE videos
           SET estado='pronto', etapa='', arquivo=?, pasta=?,
               custo_reais=?, segundos=?, terminado_em=?
         WHERE id=?
    """, (str(arquivo), str(pasta), round(custos.total_real, 4),
          round(segundos_render, 1), agora(), video["id"]))

    if video["tema_id"]:
        con.execute("UPDATE temas SET estado='usado' WHERE id = ?", (video["tema_id"],))


# ─────────────────────── erro que dá pra entender ────────────────────

# O erro cru do fornecedor não serve para quem está do outro lado da tela.
# Cada par abaixo é (pedaço que aparece na mensagem, o que dizer no lugar).
TRADUCAO: tuple[tuple[str, str], ...] = (
    ("Could not resolve authentication",
     "Falta a chave da Anthropic (ANTHROPIC_API_KEY) no arquivo .env."),
    ("ANTHROPIC_API_KEY",
     "Falta a chave da Anthropic (ANTHROPIC_API_KEY) no arquivo .env."),
    ("ELEVENLABS_API_KEY",
     "Falta a chave da ElevenLabs (ELEVENLABS_API_KEY) no arquivo .env."),
    ("GROQ_API_KEY",
     "Falta a chave da Groq (GROQ_API_KEY) no arquivo .env."),
    ("FAL_KEY",
     "Falta a chave da fal.ai (FAL_KEY) no arquivo .env."),
    ("429",
     "O fornecedor recusou por excesso de pedidos. Tente de novo em alguns minutos."),
    ("401",
     "Uma das chaves de API foi recusada. Confira se ela ainda é válida."),
    ("insufficient", "Sem crédito na conta de um dos fornecedores."),
    ("ffmpeg não encontrado",
     "O ffmpeg não está instalado no servidor — sem ele não dá para montar o vídeo."),
    ("ffmpeg falhou",
     "A montagem do vídeo falhou no ffmpeg. O material das etapas anteriores está salvo."),
)


def humanizar(erro: Exception) -> str:
    texto = str(erro)
    for pedaco, explicacao in TRADUCAO:
        if pedaco.lower() in texto.lower():
            return explicacao
    return f"Falhou na produção: {texto[:300]}"


# ──────────────────────────── trabalhador ────────────────────────────

def _pegar(con: sqlite3.Connection) -> sqlite3.Row | None:
    """Reserva o vídeo mais antigo da fila, de forma atômica."""
    cur = con.execute("""
        UPDATE videos SET estado='gerando', etapa='começando'
         WHERE id = (SELECT id FROM videos WHERE estado='na_fila'
                      ORDER BY id LIMIT 1)
        RETURNING id
    """)
    reservado = cur.fetchone()
    if reservado is None:
        return None
    return um(con, "SELECT * FROM videos WHERE id = ?", reservado["id"])


def rodar() -> None:
    """Laço do trabalhador. Roda numa thread daemon."""
    with aberto() as con:
        # Vídeo que ficou 'gerando' quando o processo caiu volta pra fila.
        con.execute("UPDATE videos SET estado='na_fila', etapa='' WHERE estado='gerando'")
        while not _parar.is_set():
            try:
                video = _pegar(con)
            except sqlite3.Error:
                traceback.print_exc()
                _parar.wait(PAUSA)
                continue

            if video is None:
                try:
                    piloto.acionar_devidos(con)
                except Exception:                             # noqa: BLE001
                    traceback.print_exc()
                _parar.wait(PAUSA)
                continue

            inicio = time.monotonic()
            try:
                produzir(con, video)
                print(f"[fila] vídeo {video['id']} pronto em "
                      f"{time.monotonic() - inicio:.0f}s")
            except Exception as erro:                       # noqa: BLE001
                traceback.print_exc()
                con.execute("""
                    UPDATE videos SET estado='falhou', etapa='', erro=?,
                                      terminado_em=? WHERE id=?
                """, (humanizar(erro), agora(), video["id"]))


def iniciar() -> threading.Thread:
    _parar.clear()
    t = threading.Thread(target=rodar, name="fila-acerolab", daemon=True)
    t.start()
    return t


def parar() -> None:
    _parar.set()
