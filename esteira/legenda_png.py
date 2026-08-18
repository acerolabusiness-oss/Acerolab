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
from .legendas import Palavra, agrupar

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
    """Um PNG por instante, com 2–4 palavras e a atual em destaque.

    `divisor_contorno` define a grossura do traço em relação ao corpo da
    letra: quanto menor o número, mais grosso o contorno. É o que separa o
    "Suave" (18) do "Impacto" (7).
    """
    pasta.mkdir(parents=True, exist_ok=True)
    corpo = int(altura * 0.058)
    traco = max(2, corpo // max(1, divisor_contorno))
    linha_base = int(altura * 0.76)          # acima da UI do TikTok/Reels
    fonte = _fonte(corpo)
    base_cor = "#FFFFFF" if cor.upper() != "#FFFFFF" else cor
    destaque_cor = cor if cor.upper() != "#FFFFFF" else "#FF3B30"
    preenchimento = (*_rgb(base_cor), 255)
    destaque = (*_rgb(destaque_cor), 255)
    borda = (*_rgb(contorno), 255)

    feitos: list[tuple[Path, Palavra]] = []
    indice = 0
    for bloco in agrupar(palavras):
        textos = [p.texto.upper() if caixa_alta else p.texto for p in bloco]
        for ativa, palavra in enumerate(bloco):
            quadro = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
            pincel = ImageDraw.Draw(quadro)
            fonte_bloco = fonte
            espaco = float(pincel.textlength(" ", font=fonte_bloco))
            larguras = [float(pincel.textlength(t, font=fonte_bloco)) for t in textos]
            total = sum(larguras) + espaco * (len(textos) - 1)
            limite = largura * 0.88
            if total > limite:
                fonte_bloco = _fonte(max(24, int(corpo * limite / total)))
                espaco = float(pincel.textlength(" ", font=fonte_bloco))
                larguras = [float(pincel.textlength(t, font=fonte_bloco)) for t in textos]
                total = sum(larguras) + espaco * (len(textos) - 1)
            x = (largura - total) / 2
            caixa = pincel.textbbox((0, 0), "Ag", font=fonte_bloco, stroke_width=traco)
            y = linha_base - (caixa[3] - caixa[1]) / 2 - caixa[1]

            for i, (texto, largura_texto) in enumerate(zip(textos, larguras)):
                pincel.text((x, y), texto, font=fonte_bloco,
                            fill=destaque if i == ativa else preenchimento,
                            stroke_width=traco, stroke_fill=borda)
                x += largura_texto + espaco

            caminho = pasta / f"palavra_{indice:04d}.png"
            quadro.save(caminho)
            feitos.append((caminho, palavra))
            indice += 1
    return feitos
