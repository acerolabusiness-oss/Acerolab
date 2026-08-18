from __future__ import annotations

import os
import sqlite3
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from esteira.direcao import cenas_com_movimento
from esteira.legendas import Palavra, agrupar
from esteira.render import fatias_por_fala
from esteira.roteiro import Cena, Roteiro
from plataforma import fila, piloto
from plataforma.banco import ESQUEMA, agora, inserir, um


def roteiro_teste(quantas: int = 10) -> Roteiro:
    cenas = []
    for indice in range(quantas):
        papel = ("gancho" if indice == 0 else
                 "virada" if indice == quantas - 3 else
                 "final" if indice == quantas - 1 else "contexto")
        cenas.append(Cena(
            narracao=f"Esta é a fala curta da cena {indice}.",
            imagem="A concrete vertical scene",
            movimento="slow pan right",
            plano="medio",
            papel=papel,
            energia=5 if papel != "contexto" else 2,
        ))
    return Roteiro(titulo="Teste", promessa="Uma descoberta", paleta="red and black",
                   som_ambiente="wind", cenas=cenas)


class DirecaoTest(unittest.TestCase):
    def test_hibrido_sempre_move_gancho_e_final(self):
        escolhidas = cenas_com_movimento(roteiro_teste())
        self.assertIn(0, escolhidas)
        self.assertIn(1, escolhidas)
        self.assertIn(9, escolhidas)
        self.assertEqual(len(escolhidas), 4)

    def test_cortes_seguem_a_fala_e_preservam_duracao(self):
        roteiro = roteiro_teste()
        palavras = [Palavra(f"p{i}", i * .18, i * .18 + .15) for i in range(60)]
        fatias = fatias_por_fala(roteiro, palavras, 10.8)
        self.assertEqual(len(fatias), 10)
        self.assertAlmostEqual(sum(fatias), 10.8, places=2)

    def test_legenda_mantem_contexto_curto(self):
        palavras = [Palavra(texto, i * .2, i * .2 + .18)
                    for i, texto in enumerate("um bloco curto fica mais legível.".split())]
        blocos = agrupar(palavras)
        self.assertTrue(all(1 <= len(bloco) <= 4 for bloco in blocos))
        self.assertEqual(sum(map(len, blocos)), len(palavras))

    def test_som_viral_nunca_entra_no_mp4(self):
        serie = {
            "nicho_texto": "história", "idioma": "pt-BR", "voz": "",
            "musicas": '["pulso-noturno.mp3"]', "modo_musica": "biblioteca",
            "estilo": "cinematografico", "modo": "automatico",
            "modelo_video": "wan", "duracao": "curto",
        }

        com_trilha = fila.montar_serie(serie, {"modo_musica": "biblioteca"})
        para_viral = fila.montar_serie(serie, {"modo_musica": "viral"})

        self.assertIsNotNone(com_trilha.musica_fundo)
        self.assertIsNone(para_viral.musica_fundo)


class PilotoTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:", isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)

    def tearDown(self):
        self.con.close()

    def test_piloto_cria_um_video_e_avanca_o_relogio(self):
        usuario = inserir(self.con,
            "INSERT INTO usuarios(email,senha,nome,criado_em) VALUES(?,?,?,?)",
            "piloto@teste.local", "x", "Piloto", agora())
        serie = inserir(self.con, """
            INSERT INTO series
              (usuario_id,nome,nicho,nicho_texto,idioma,voz,musicas,estilo,
               legenda,duracao,modo,modelo_video,piloto_ativo,frequencia,
               proxima_geracao,criada_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, usuario, "Série", "historia", "historia", "pt-BR", "", "[]",
             "cinematografico", "traco-forte", "curto", "automatico", "wan",
             1, "diario", agora(), agora())
        tema = inserir(self.con, """
            INSERT INTO temas(serie_id,titulo,gancho,estado,criado_em)
            VALUES(?,?,?,'proposto',?)
        """, serie, "Tema pronto", "Gancho", agora())

        with patch.dict(os.environ, {"ACEROLAB_ALLOW_UNPAID": "1"}):
            self.assertEqual(piloto.acionar_devidos(self.con), 1)
            self.assertEqual(piloto.acionar_devidos(self.con), 0)

        video = um(self.con, "SELECT * FROM videos WHERE serie_id=?", serie)
        self.assertIsNotNone(video)
        self.assertEqual(video["tema_id"], tema)
        self.assertEqual(video["modo_musica"], "biblioteca")
        self.assertEqual(video["plataforma_musica"], "")
        relogio = um(self.con, "SELECT proxima_geracao FROM series WHERE id=?", serie)
        self.assertGreater(relogio["proxima_geracao"], agora())

        # Se o relógio vencer enquanto o vídeo ainda está na fila, o piloto
        # não perde o ciclo: deixa a data vencida para tentar assim que acabar.
        vencido = agora()
        self.con.execute("UPDATE series SET proxima_geracao=? WHERE id=?",
                         (vencido, serie))
        with patch.dict(os.environ, {"ACEROLAB_ALLOW_UNPAID": "1"}):
            self.assertEqual(piloto.acionar_devidos(self.con), 0)
        mantido = um(self.con, "SELECT proxima_geracao FROM series WHERE id=?", serie)
        self.assertEqual(mantido["proxima_geracao"], vencido)

    def test_progresso_da_etapa_nunca_volta(self):
        usuario = inserir(self.con,
            "INSERT INTO usuarios(email,senha,nome,criado_em) VALUES(?,?,?,?)",
            "progresso@teste.local", "x", "Progresso", agora())
        serie = inserir(self.con, """
            INSERT INTO series
              (usuario_id,nome,nicho,nicho_texto,idioma,voz,musicas,estilo,
               legenda,duracao,modo,modelo_video,criada_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, usuario, "Série", "historia", "historia", "pt-BR", "", "[]",
             "cinematografico", "traco-forte", "curto", "automatico", "wan",
             agora())
        video = inserir(self.con, """
            INSERT INTO videos(serie_id,usuario_id,criado_em) VALUES(?,?,?)
        """, serie, usuario, agora())
        fila._etapa(self.con, video, "renderizando vídeo", 84)
        fila._etapa(self.con, video, "evento atrasado", 24)
        estado = um(self.con, "SELECT etapa, progresso FROM videos WHERE id=?", video)
        self.assertEqual(estado["etapa"], "renderizando vídeo")
        self.assertEqual(estado["progresso"], 84)

    def test_falha_de_pauta_reagenda_sem_perder_a_semana(self):
        usuario = inserir(self.con,
            "INSERT INTO usuarios(email,senha,nome,criado_em) VALUES(?,?,?,?)",
            "reagenda@teste.local", "x", "Reagenda", agora())
        serie = inserir(self.con, """
            INSERT INTO series
              (usuario_id,nome,nicho,nicho_texto,idioma,voz,musicas,estilo,
               legenda,duracao,modo,modelo_video,piloto_ativo,frequencia,
               proxima_geracao,criada_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, usuario, "Série", "historia", "historia", "pt-BR", "", "[]",
             "cinematografico", "traco-forte", "curto", "automatico", "wan",
             1, "semanal", agora(), agora())

        with (patch.dict(os.environ, {"ACEROLAB_ALLOW_UNPAID": "1"}),
              patch("plataforma.piloto.temas.propor",
                    side_effect=RuntimeError("fornecedor indisponível"))):
            self.assertEqual(piloto.acionar_devidos(self.con), 0)

        self.assertIsNone(um(self.con, "SELECT id FROM videos WHERE serie_id=?", serie))
        reagendada = um(self.con, "SELECT proxima_geracao FROM series WHERE id=?", serie)
        espera = datetime.fromisoformat(reagendada["proxima_geracao"]) - datetime.now(timezone.utc)
        self.assertGreater(espera.total_seconds(), 0)
        self.assertLess(espera.total_seconds(), 20 * 60)


if __name__ == "__main__":
    unittest.main()
