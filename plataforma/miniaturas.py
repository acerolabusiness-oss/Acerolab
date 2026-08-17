"""Gera uma amostra real de cada estilo visual, uma vez só.

    .venv/bin/python -m plataforma.miniaturas

A ClipShort mostra só o nome do estilo — "Expressionismo", "Carvão" — e
ninguém escolhe às cegas. Aqui cada estilo aparece com uma imagem feita
pelo mesmo modelo que vai produzir os vídeos, então o que o cliente vê na
hora de escolher é o que ele vai receber.

Custo: nove imagens, uma vez na vida do produto. Depois é arquivo estático.
Use `--refazer` para trocar a amostra de um estilo que não ficou bom.
"""
from __future__ import annotations

import argparse
import os
import sys
from io import BytesIO

import requests
from PIL import Image

from esteira.config import MODELO_IMAGEM, Ambiente, carregar_env

from .catalogo import ESTILOS, MINIATURAS

# Uma cena só, igual para todos: a diferença entre as miniaturas tem que ser
# o estilo, não o assunto. Assim a comparação lado a lado é honesta.
CENA = ("a lone figure standing at the entrance of a vast hall, "
        "looking up, dramatic light from above, vertical composition")

LARGURA, ALTURA = 576, 896      # 0,52 MP por imagem: barato e nítido no card


def uma(estilo, sessao: requests.Session, refazer: bool) -> str:
    destino = MINIATURAS / f"{estilo.chave}.webp"
    if destino.exists() and not refazer:
        return "já existe"

    r = sessao.post(
        f"https://fal.run/{MODELO_IMAGEM}",
        json={"prompt": f"{CENA}. {estilo.prompt}",
              "image_size": {"width": LARGURA, "height": ALTURA},
              "num_images": 1},
        headers={"Authorization": f"Key {os.environ['FAL_KEY']}"},
        timeout=180,
    )
    r.raise_for_status()
    url = r.json()["images"][0]["url"]

    bruto = sessao.get(url, timeout=120)
    bruto.raise_for_status()

    # webp com qualidade 82 deixa cada card em ~40 KB — nove deles não pesam
    # nada, e a tela de escolha é a primeira impressão do produto.
    imagem = Image.open(BytesIO(bruto.content)).convert("RGB")
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem.save(destino, "WEBP", quality=82, method=6)
    return f"{destino.stat().st_size // 1024} KB"


def main(argv: list[str] | None = None) -> int:
    carregar_env()
    p = argparse.ArgumentParser(prog="plataforma.miniaturas", description=__doc__)
    p.add_argument("--refazer", action="store_true", help="regera mesmo se já existir")
    p.add_argument("--so", default="", help="chave de um estilo só")
    args = p.parse_args(argv)

    if Ambiente().fal is None:
        print("Falta FAL_KEY no .env — sem ela não dá para gerar amostra.",
              file=sys.stderr)
        return 1

    alvos = [e for e in ESTILOS if not args.so or e.chave == args.so]
    if not alvos:
        print(f"estilo desconhecido: {args.so}", file=sys.stderr)
        return 1

    with requests.Session() as sessao:
        for estilo in alvos:
            print(f"  {estilo.nome:.<24}", end="", flush=True)
            try:
                print(" " + uma(estilo, sessao, args.refazer))
            except Exception as erro:                        # noqa: BLE001
                print(f" FALHOU: {erro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
