"""Gera o pacote de logotipos da ACEROLAB em arquivos soltos.

    python site/logos.py

Até agora a marca só existia dentro da landing e do favicon — não dava para
mandar para ninguém. Aqui ela sai como arquivo: SVG para usar em qualquer
lugar e PNG para onde SVG não entra (perfil de rede social, anúncio,
apresentação).

O desenho não é decalque: a fruta é um círculo modulado por cos(3θ) — os
três gomos rasos da acerola — e o play é um triângulo com os cantos
arredondados, recortado dela pela regra `evenodd`. Por isso tudo nasce de
`marca.py`, e mudar a fruta é mudar um número lá, não redesenhar curva.
"""
from __future__ import annotations

import math
import pathlib
import sys

from montar import wordmark          # noqa: E402  (mesma pasta)

AQUI = pathlib.Path(__file__).parent
DESTINO = AQUI.parent / "marca"

ACEROLA = "#D31C33"
FOLHA = "#3F6B4E"        # verde-acerola, o mesmo da landing
TINTA = "#17171A"
BRANCO = "#FFFFFF"

# O recorte vem do marca.txt, junto com os traçados: se a fruta mudar de
# tamanho, o enquadramento acompanha sem ninguém precisar lembrar.


def pedacos() -> dict[str, str]:
    dados = {}
    for linha in (AQUI / "marca.txt").read_text().strip().splitlines():
        chave, valor = linha.split("=", 1)
        dados[chave] = valor
    return dados


def recorte(p: dict[str, str]) -> tuple[float, float, float, float]:
    return tuple(float(n) for n in p["VIEWBOX"].split())    # type: ignore[return-value]


def marca_svg(fruta_cor: str, folha_cor: str) -> str:
    p = pedacos()
    x, y, l, a = recorte(p)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {l} {a}" width="{l}" height="{a}">
  <path d="{p['FOLHA']}" fill="{folha_cor}"/>
  <path d="{p['TALO']}" fill="none" stroke="{folha_cor}" stroke-width="4.6" stroke-linecap="round"/>
  <path d="{p['FRUTA']} {p['PLAY']}" fill-rule="evenodd" fill="{fruta_cor}"/>
</svg>'''


def assinatura_svg(fruta_cor: str, folha_cor: str, texto_cor: str) -> str:
    """Marca + palavra, alinhadas pela altura do x — não pela caixa da fonte,
    que deixaria a fruta parecendo alta demais."""
    p = pedacos()
    wm = wordmark(AQUI / "Outfit.ttf", 800, "acerolab")
    bx0, by0, bx1, by1 = wm["bbox"]
    larg_wm, alt_wm = bx1 - bx0, by1 - by0

    vx, vy, vl, va = recorte(p)
    alt_marca = 78.0                                   # altura da fruta na assinatura
    escala = alt_marca / va
    larg_marca = vl * escala
    vao = alt_marca * 0.30

    escala_wm = (alt_marca * 0.60) / alt_wm            # palavra menor que a fruta
    largura = larg_marca + vao + larg_wm * escala_wm
    altura = alt_marca
    topo_wm = (altura - alt_wm * escala_wm) / 2

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura:.1f} {altura:.1f}" width="{largura:.0f}" height="{altura:.0f}">
  <g transform="translate(0 0) scale({escala:.5f}) translate({-vx} {-vy})">
    <path d="{p['FOLHA']}" fill="{folha_cor}"/>
    <path d="{p['TALO']}" fill="none" stroke="{folha_cor}" stroke-width="4.6" stroke-linecap="round"/>
    <path d="{p['FRUTA']} {p['PLAY']}" fill-rule="evenodd" fill="{fruta_cor}"/>
  </g>
  <g transform="translate({larg_marca + vao:.2f} {topo_wm:.2f}) scale({escala_wm:.5f}) translate({-bx0:.2f} {-by0:.2f})">
    <path d="{wm['d']}" fill="{texto_cor}"/>
  </g>
</svg>'''


ARQUIVOS: tuple[tuple[str, str], ...] = (
    # marca sozinha
    ("marca.svg",           "marca_cor"),
    ("marca-branca.svg",    "marca_branca"),
    ("marca-preta.svg",     "marca_preta"),
    # assinatura (marca + palavra)
    ("assinatura.svg",        "assinatura_cor"),
    ("assinatura-branca.svg", "assinatura_branca"),
    ("assinatura-preta.svg",  "assinatura_preta"),
)


def montar() -> dict[str, str]:
    return {
        "marca_cor":          marca_svg(ACEROLA, FOLHA),
        "marca_branca":       marca_svg(BRANCO, BRANCO),
        "marca_preta":        marca_svg(TINTA, TINTA),
        "assinatura_cor":     assinatura_svg(ACEROLA, FOLHA, TINTA),
        "assinatura_branca":  assinatura_svg(BRANCO, BRANCO, BRANCO),
        "assinatura_preta":   assinatura_svg(TINTA, TINTA, TINTA),
    }


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    feitos = montar()
    for arquivo, chave in ARQUIVOS:
        alvo = DESTINO / arquivo
        alvo.write_text(feitos[chave], encoding="utf-8")
        print(f"  {arquivo:26} {alvo.stat().st_size // 1024 or 1} KB")
    print(f"\n{len(ARQUIVOS)} arquivos em {DESTINO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
