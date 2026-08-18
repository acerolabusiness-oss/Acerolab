from __future__ import annotations

import os
import sqlite3
import unittest
from unittest.mock import patch

from esteira.direcao import cenas_com_movimento
from esteira.legendas import Palavra, agrupar
from esteira.render import fatias_por_fala
from esteira.roteiro import Cena, Roteiro
from plataforma import piloto
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
        self.assertIn(9, escolhidas)
        self.assertGreaterEqual(len(escolhidas), 4)

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
        relogio = um(self.con, "SELECT proxima_geracao FROM series WHERE id=?", serie)
        self.assertGreater(relogio["proxima_geracao"], agora())


if __name__ == "__main__":
    unittest.main()
