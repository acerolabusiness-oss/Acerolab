"""Orquestrador da esteira.

    python -m esteira --nicho "curiosidades da história" --repetir 50

Roda a esteira inteira N vezes e imprime o custo real por vídeo. Esse número
é o que decide se a operação fecha com os 20% de royalty.
"""
from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import clipes as etapa_clipes
from . import direcao as etapa_direcao
from . import imagens as etapa_imagens
from . import legenda_png as etapa_legenda_png
from . import legendas as etapa_legendas
from . import narracao as etapa_narracao
from . import render as etapa_render
from . import roteiro as etapa_roteiro
from .config import SAIDA, Ambiente, Precos, Serie, carregar_env
from .custos import Custos, consolidar


def um_video(serie: Serie, pasta: Path, precos: Precos, indice: int,
             modo: str = "imagem", modelo_video: str = "wan",
             segundos_por_cena: float = 5.0) -> Custos:
    custos = Custos(precos=precos)
    pasta.mkdir(parents=True, exist_ok=True)

    print(f"  [{indice}] roteiro...", end="", flush=True)
    roteiro = etapa_roteiro.gerar(serie, custos)
    print(f" {roteiro.titulo!r}")

    if modo == "video":
        print(f"  [{indice}] {len(roteiro.cenas)} clipes ({modelo_video})...",
              end="", flush=True)
        quadros = etapa_clipes.gerar(roteiro, serie, pasta / "cenas", custos,
                                     modelo=modelo_video,
                                     segundos_por_cena=segundos_por_cena)
    elif modo == "automatico":
        print(f"  [{indice}] direção automática...", end="", flush=True)
        quadros = etapa_imagens.gerar(roteiro, serie, pasta / "cenas", custos)
        indices = etapa_direcao.cenas_com_movimento(roteiro)
        try:
            movimentos = etapa_clipes.gerar(
                roteiro, serie, pasta / "cenas", custos, modelo=modelo_video,
                segundos_por_cena=segundos_por_cena, indices=indices,
                tolerar_falhas=True)
            for caminho in movimentos:
                i = int(caminho.stem.rsplit("_", 1)[-1])
                quadros[i] = caminho
        except Exception as erro:  # a imagem já gerada é o fallback seguro
            print(f" clipes indisponíveis ({erro}); usando imagens", end="")
    else:
        print(f"  [{indice}] {len(roteiro.cenas)} imagens...", end="", flush=True)
        quadros = etapa_imagens.gerar(roteiro, serie, pasta / "cenas", custos)
    print(" ok")

    print(f"  [{indice}] narração...", end="", flush=True)
    audio, _ = etapa_narracao.gerar(roteiro, serie, pasta / "narracao.mp3", custos)
    print(" ok")

    legenda = None
    palavras = []
    if serie.legenda:
        print(f"  [{indice}] legendas...", end="", flush=True)
        palavras = etapa_legendas.transcrever(audio, serie.idioma, custos)
        if etapa_render.tem_libass():
            legenda = etapa_legendas.escrever_ass(
                palavras, pasta / "legenda.ass", serie.largura, serie.altura
            )
        else:
            # build sem libass: cada palavra vira PNG e entra por overlay
            legenda = etapa_legenda_png.desenhar(
                palavras, pasta / "legenda", serie.largura, serie.altura
            )
        print(f" {len(palavras)} palavras")

    print(f"  [{indice}] render...", end="", flush=True)
    video, segundos = etapa_render.montar(
        quadros, audio, legenda, serie, pasta / "video.mp4",
        roteiro=roteiro, palavras=palavras,
    )
    # Render não custa API, mas custa CPU. Fica registrado com valor zero
    # para aparecer no relatório e ninguém esquecer que existe.
    custos.registrar("render", "segundos", segundos, 0.0,
                     f"{segundos:.1f}s de CPU (custo de servidor, não de API)")
    print(f" {segundos:.1f}s")

    (pasta / "roteiro.json").write_text(roteiro.model_dump_json(indent=2), encoding="utf-8")
    custos.salvar(pasta / "custo.json")
    print(f"  [{indice}] {video}  —  R$ {custos.total_real:.4f}\n")
    return custos


def main(argv: list[str] | None = None) -> int:
    carregar_env()
    p = argparse.ArgumentParser(prog="esteira", description=__doc__)
    p.add_argument("--nicho", required=True, help="tema da série")
    p.add_argument("--cenas", type=int, default=10, help="batidas visuais (padrão: 10)")
    p.add_argument("--repetir", type=int, default=1, help="quantos vídeos gerar")
    p.add_argument("--largura", type=int, default=1080)
    p.add_argument("--altura", type=int, default=1920)
    p.add_argument("--idioma", default="pt-BR")
    # O wizard já deixa escolher estilo visual; a CLI não deixava, e por isso
    # todo teste saía no padrão "cinematográfico" — foto realista. Aceita o
    # prompt cru, para dar para experimentar estilo que ainda não está no
    # catálogo antes de virar opção do produto.
    p.add_argument("--estilo", default="", help="prompt de estilo visual das cenas")
    p.add_argument("--voz", default="", help="id da voz na ElevenLabs")
    p.add_argument("--musica", type=Path, default=None, help="mp3 de fundo")
    p.add_argument("--sem-legenda", action="store_true")
    p.add_argument("--dolar", type=float, default=5.00)
    p.add_argument("--modo", choices=["automatico", "imagem", "video"],
                   default="automatico",
                   help="direção híbrida, imagem ou clipe em todas as cenas")
    p.add_argument("--modelo-video", choices=list(etapa_clipes.MODELOS),
                   default="wan", help="só vale com --modo video")
    p.add_argument("--segundos-cena", type=float, default=5.0,
                   help="duração de cada clipe; é o que a fal.ai cobra")
    args = p.parse_args(argv)

    faltando = Ambiente().faltando()
    if faltando:
        print("Faltam chaves no .env:", ", ".join(faltando), file=sys.stderr)
        print("Copie .env.exemplo para .env e preencha.", file=sys.stderr)
        return 1

    serie = Serie(
        nicho=args.nicho, idioma=args.idioma, voz=args.voz,
        musica_fundo=args.musica, cenas=args.cenas,
        legenda=not args.sem_legenda,
        largura=args.largura, altura=args.altura,
        **({"estilo": args.estilo} if args.estilo else {}),
    )
    precos = Precos(dolar=args.dolar)

    lote = SAIDA / datetime.now().strftime("%Y%m%d-%H%M%S")
    print(f"\nnicho: {serie.nicho}")
    print(f"modo: {args.modo}", end="")
    if args.modo == "video":
        spec = etapa_clipes.MODELOS[args.modelo_video]
        preco = (f"US$ {spec['dolar_por_clipe']}/clipe"
                 if "dolar_por_clipe" in spec
                 else f"US$ {spec['dolar_por_segundo']}/s")
        print(f" ({args.modelo_video}, {preco} x {serie.cenas} cenas)")
    else:
        print("")
    print(f"formato: {serie.largura}x{serie.altura} ({serie.megapixels:.2f} MP por imagem)")
    print(f"saída: {lote}\n")

    coletados: list[Custos] = []
    falhas = 0
    for i in range(1, args.repetir + 1):
        try:
            coletados.append(um_video(
                serie, lote / f"video_{i:03d}", precos, i,
                modo=args.modo, modelo_video=args.modelo_video,
                segundos_por_cena=args.segundos_cena,
            ))
        except Exception as erro:                      # noqa: BLE001
            falhas += 1
            print(f"  [{i}] FALHOU: {erro}\n")
            traceback.print_exc(file=sys.stderr)

    print(consolidar(coletados, precos))
    if falhas:
        # Falha custa dinheiro: o que já rodou antes do erro foi cobrado.
        print(f"\n  {falhas} de {args.repetir} falharam — o gasto delas não entra na média acima.")
    return 0 if coletados else 1


if __name__ == "__main__":
    raise SystemExit(main())
