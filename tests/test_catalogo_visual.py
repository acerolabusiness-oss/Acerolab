"""Regressões do catálogo visual e das prévias de voz."""
from __future__ import annotations

import unittest

from esteira.config import RAIZ
from plataforma.catalogo import NICHOS, VOZES, musicas_disponiveis


class CatalogoVisualTest(unittest.TestCase):
    def test_cada_nicho_tem_uma_capa_propria_instalada(self) -> None:
        capas = [n.capa for n in NICHOS]

        self.assertEqual(len(capas), 14)
        self.assertEqual(len(set(capas)), len(capas))
        for capa in capas:
            caminho = RAIZ / "plataforma" / capa.removeprefix("/")
            # A URL começa em /estatico, já dentro da pasta plataforma.
            self.assertTrue(caminho.is_file(), capa)

    def test_vozes_tem_ids_unicos(self) -> None:
        ids = [v.id for v in VOZES]
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(set(ids)), len(ids))

    def test_grade_mobile_nao_amplia_capas_nem_controles(self) -> None:
        css = (RAIZ / "plataforma" / "estatico" / "estilo.css").read_text()

        self.assertIn(
            ".nichos-visuais{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}",
            css,
        )
        self.assertIn(
            "input[type=text],input[type=email],input[type=password],select,textarea{font-size:16px}",
            css,
        )
        self.assertNotIn(
            "@media (max-width:460px){.nichos-visuais{grid-template-columns:1fr}}",
            css,
        )

    def test_trilhas_instaladas_sao_mp3_cc0(self) -> None:
        trilhas = {t.arquivo: t for t in musicas_disponiveis()}
        esperadas = {
            "melodia-sinistra.mp3",
            "misterio-sem-solucao.mp3",
            "calmaria.mp3",
            "horizonte.mp3",
            "respiro.mp3",
        }

        self.assertTrue(esperadas.issubset(trilhas))
        for nome in esperadas:
            trilha = trilhas[nome]
            self.assertEqual(trilha.caminho.suffix, ".mp3")
            self.assertGreater(trilha.caminho.stat().st_size, 1_000_000)
            self.assertEqual(trilha.autor, "John Bartmann")
            self.assertEqual(trilha.licenca, "CC0")


if __name__ == "__main__":
    unittest.main()
