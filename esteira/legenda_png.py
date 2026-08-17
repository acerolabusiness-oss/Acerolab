"""Legenda sem libass.

Muitas builds de ffmpeg vêm sem libass e sem freetype — a do Mac deste
projeto é uma delas — e aí `subtitles` e `drawtext` simplesmente não
existem. Aqui cada palavra vira um PNG transparente desenhado pelo Pillow e
entra por `overlay`, filtro que existe em qualquer build.

Vantagem extra: a tipografia é a da marca, não a que o sistema tiver, e o
estilo escolhido no wizard vira parâmetro de verdade em vez de enfeite.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import RAIZ
from .legendas import Palavra

FONTE = RAIZ / "recursos" / "Outfit.ttf"


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    if FONTE.exists():
        fonte = ImageFont.truetype(str(FONTE), tamanho)
        try:
            fonte.set_variation_by_name(b"Black")
        except (AttributeError, OSError):
            try:
                fonte.set_variation_by_name(b"Bold")
            except (AttributeError, OSError):
                pass
        return fonte
    return ImageFont.load_default(tamanho)


def _rgb(cor: str) -> tuple[int, int, int]:
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def desenhar(palavras: list[Palavra], pasta: Path,
             largura: int, altura: int,
             cor: str = "#FFFFFF", contorno: str = "#000000",
             caixa_alta: bool = True,
             divisor_contorno: int = 10) -> list[tuple[Path, Palavra]]:
    """Um PNG por palavra, já do tamanho do quadro, com contorno.

    `divisor_contorno` define a grossura do traço em relação ao corpo da
    letra: quanto menor o número, mais grosso o contorno. É o que separa o
    "Suave" (18) do "Impacto" (7).
    """
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = int(altura * 0.058)
    traco = max(2, corpo // max(1, divisor_contorno))
    linha_base = int(altura * 0.76)          # acima da UI do TikTok/Reels
    fonte = _fonte(corpo)
    preenchimento = (*_rgb(cor), 255)
    borda = (*_rgb(contorno), 255)

    feitos: list[tuple[Path, Palavra]] = []
    for i, palavra in enumerate(palavras):
        texto = palavra.texto.upper() if caixa_alta else palavra.texto
        quadro = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
        pincel = ImageDraw.Draw(quadro)

        caixa = pincel.textbbox((0, 0), texto, font=fonte, stroke_width=traco)
        x = (largura - (caixa[2] - caixa[0])) // 2 - caixa[0]
        y = linha_base - (caixa[3] - caixa[1]) // 2 - caixa[1]

        pincel.text((x, y), texto, font=fonte, fill=preenchimento,
                    stroke_width=traco, stroke_fill=borda)

        caminho = pasta / f"palavra_{i:04d}.png"
        quadro.save(caminho)
        feitos.append((caminho, palavra))
    return feitos
