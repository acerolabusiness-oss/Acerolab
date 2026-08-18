"""Regressões do catálogo visual e das prévias de voz."""
from __future__ import annotations

import unittest

from esteira.config import RAIZ
from plataforma.catalogo import NICHOS, VOZES


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


if __name__ == "__main__":
    unittest.main()
