"""Regressões do catálogo visual e das prévias de voz."""
from __future__ import annotations

import unittest

from esteira.config import RAIZ
from plataforma.catalogo import (NICHOS, SONS_PLATAFORMA, VOZES,
                                 configurar_musica, musicas_disponiveis)


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

    def test_pacote_de_vibe_atual_esta_instalado_e_liberado(self) -> None:
        trilhas = {t.arquivo: t for t in musicas_disponiveis()}
        atuais = {
            "pulso-noturno.mp3",
            "lofi-depois-da-meia-noite.mp3",
            "rua-em-movimento.mp3",
            "neon-acelerado.mp3",
            "onda-de-verao.mp3",
        }

        self.assertTrue(atuais.issubset(trilhas))
        for nome in atuais:
            trilha = trilhas[nome]
            self.assertTrue(trilha.destaque)
            self.assertEqual(trilha.autor, "Loyalty Freak Music")
            self.assertEqual(trilha.licenca, "CC0")
            self.assertGreater(trilha.caminho.stat().st_size, 1_000_000)

    def test_modo_viral_usa_catalogo_oficial_e_filtra_arquivo_inventado(self) -> None:
        disponivel = musicas_disponiveis()[0].arquivo
        modo, plataforma, musicas = configurar_musica(
            "viral", "youtube", [disponivel, "nao-existe.mp3", disponivel])

        self.assertEqual((modo, plataforma), ("viral", "youtube"))
        self.assertEqual(musicas, [disponivel])
        self.assertEqual({p.chave for p in SONS_PLATAFORMA},
                         {"tiktok", "instagram", "youtube"})
        for plataforma_som in SONS_PLATAFORMA:
            self.assertTrue(plataforma_som.url_ouvir.startswith("https://"))
            self.assertTrue(plataforma_som.rotulo_ouvir)

    def test_wizard_explica_que_som_viral_nao_e_embutido(self) -> None:
        html = (RAIZ / "plataforma" / "paginas" / "wizard.html").read_text()

        self.assertIn("Som viral da plataforma", html)
        self.assertIn("O áudio viral não é embutido no arquivo", html)
        self.assertIn('data-audio-painel="viral"', html)
        self.assertIn("ouvir-plataforma", html)
        self.assertIn("if (document.hidden) pararAtual()", html)
        self.assertIn("window.addEventListener('pagehide', pararAtual)", html)


if __name__ == "__main__":
    unittest.main()
