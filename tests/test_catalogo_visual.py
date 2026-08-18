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

    def test_wizard_mobile_usa_nichos_compactos_e_carrossel_visual(self) -> None:
        css = (RAIZ / "plataforma" / "estatico" / "estilo.css").read_text()

        self.assertIn(
            ".nichos-texto{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}",
            css,
        )
        self.assertIn("grid-auto-columns:min(76vw,292px)", css)
        self.assertIn("scroll-snap-type:x mandatory", css)
        self.assertIn(
            "input[type=text],input[type=email],input[type=password],select,textarea{font-size:16px}",
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

    def test_wizard_simplifica_inicio_e_conserva_padrao_automatico(self) -> None:
        html = (RAIZ / "plataforma" / "paginas" / "wizard.html").read_text()

        self.assertEqual(html.count("<section data-passo hidden>"), 4)
        self.assertNotIn('class="nicho-capa"', html)
        self.assertNotIn("Estratégia de áudio", html)
        self.assertIn('name="modo_musica" value="biblioteca"', html)
        self.assertIn('name="modo" value="automatico"', html)
        self.assertIn("Você pode mudar tudo depois na central da série", html)
        self.assertIn("dica-arraste", html)
        self.assertIn("if (document.hidden) pararAtual()", html)
        self.assertIn("window.addEventListener('pagehide', pararAtual)", html)


if __name__ == "__main__":
    unittest.main()
