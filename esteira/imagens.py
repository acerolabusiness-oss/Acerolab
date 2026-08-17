"""Etapa 2 — imagens, com Z-Image Turbo na fal.ai.

A fal cobra POR MEGAPIXEL (US$ 0,005/MP), não por imagem. Uma vertical cheia
de 1080x1920 tem 2,07 MP e custa ~US$ 0,0104 — mais de 3x o que uma tabela
baseada em "US$ 0,003 por imagem" prevê. Por isso a resolução é parâmetro.
"""
from __future__ import annotations

import concurrent.futures as futuros
import os
from pathlib import Path

import requests

from .config import MODELO_IMAGEM, Serie
from .custos import Custos
from .roteiro import Roteiro

ENDPOINT = f"https://fal.run/{MODELO_IMAGEM}"
NEGATIVO = "text, watermark, logo, signature, blurry, low quality, deformed hands"


def _uma(prompt: str, serie: Serie, destino: Path, sessao: requests.Session) -> Path:
    corpo = {
        "prompt": f"{prompt}. {serie.estilo}",
        "negative_prompt": NEGATIVO,
        "image_size": {"width": serie.largura, "height": serie.altura},
        "num_images": 1,
        "enable_safety_checker": True,
    }
    r = sessao.post(
        ENDPOINT,
        json=corpo,
        headers={"Authorization": f"Key {os.environ['FAL_KEY']}"},
        timeout=180,
    )
    r.raise_for_status()
    url = r.json()["images"][0]["url"]

    binario = sessao.get(url, timeout=180)
    binario.raise_for_status()
    destino.write_bytes(binario.content)
    return destino


def gerar(roteiro: Roteiro, serie: Serie, pasta: Path, custos: Custos) -> list[Path]:
    """Gera uma imagem por cena. Em paralelo — são chamadas independentes."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos: list[Path] = [pasta / f"cena_{i:02d}.jpg" for i in range(len(roteiro.cenas))]

    with requests.Session() as sessao:
        with futuros.ThreadPoolExecutor(max_workers=4) as pool:
            tarefas = {
                pool.submit(_uma, cena.imagem, serie, caminho, sessao): caminho
                for cena, caminho in zip(roteiro.cenas, caminhos)
            }
            for tarefa in futuros.as_completed(tarefas):
                tarefa.result()   # propaga a exceção da thread

    custos.imagem(serie.megapixels, len(caminhos))
    return caminhos
