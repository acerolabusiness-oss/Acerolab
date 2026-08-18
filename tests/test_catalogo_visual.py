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


if __name__ == "__main__":
    unittest.main()
