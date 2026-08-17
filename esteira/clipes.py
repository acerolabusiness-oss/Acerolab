"""Etapa 2b — cenas em VÍDEO, não em imagem estática.

A diferença de custo entre este arquivo e `imagens.py` é a decisão econômica
mais importante do projeto:

    imagem estática : cobrada por megapixel   → centavos de dólar por vídeo
    vídeo gerado    : cobrado por SEGUNDO     → dólares por vídeo

No modelo mais barato do mercado (US$ 0,05/s), 35 segundos de vídeo custam
US$ 1,75 — contra os US$ 0,052 que a tabela do franqueador prevê para o
vídeo inteiro. É por isso que a esteira roda nos dois modos: para a medição
comparar lado a lado em vez de discutir no achismo.
"""
from __future__ import annotations

import concurrent.futures as futuros
import os
import time
from pathlib import Path

import requests

from .config import Serie
from .custos import Custos
from .roteiro import Roteiro

# Catálogo do que dá para usar. O preço é por segundo de vídeo gerado.
MODELOS: dict[str, dict] = {
    "wan": {
        "rota": "fal-ai/wan-25-preview/text-to-video",
        # O Wan cobra POR RESOLUÇÃO, e o código pedia 720p pagando como 480p.
        # A página do modelo em 16/08/2026: $0,05/s em 480p, $0,10/s em 720p,
        # $0,15/s em 1080p. A fatura de 7 clipes de 5s em 720p veio $3,50,
        # que é exatamente 35s x $0,10. Quem mexer na resolução tem que mexer
        # no preço junto, senão a tela do wizard volta a mentir.
        "dolar_por_segundo_por_resolucao": {"480p": 0.05, "720p": 0.10, "1080p": 0.15},
        "dolar_por_segundo": 0.10,      # o que a esteira usa hoje: 720p
        "nota": "preço conferido na fatura; varia com a resolução",
    },
    "seedance": {
        "rota": "fal-ai/bytedance/seedance/v1/pro/text-to-video",
        "dolar_por_segundo": 0.052,
        "nota": "~US$ 0,26 por clipe de 5s em 720p",
    },
    "kling": {
        "rota": "fal-ai/kling-video/v2/master/text-to-video",
        "dolar_por_segundo": 0.224,
        "nota": "qualidade alta, preço alto",
    },
}


def _um(prompt: str, serie: Serie, segundos: float, modelo: dict,
        destino: Path, sessao: requests.Session) -> Path:
    r = sessao.post(
        f"https://fal.run/{modelo['rota']}",
        json={
            "prompt": f"{prompt}. {serie.estilo}",
            "duration": max(5, int(round(segundos))),   # os modelos trabalham em passos de segundo
            "aspect_ratio": "9:16",
            "resolution": "720p",
        },
        headers={"Authorization": f"Key {os.environ['FAL_KEY']}"},
        timeout=900,          # geração de vídeo demora minutos, não segundos
    )
    r.raise_for_status()
    dados = r.json()
    url = dados["video"]["url"] if "video" in dados else dados["videos"][0]["url"]

    binario = sessao.get(url, timeout=900)
    binario.raise_for_status()
    destino.write_bytes(binario.content)
    return destino


def gerar(roteiro: Roteiro, serie: Serie, pasta: Path, custos: Custos,
          modelo: str = "wan", segundos_por_cena: float = 5.0) -> list[Path]:
    """Um clipe de vídeo por cena."""
    if modelo not in MODELOS:
        raise ValueError(f"modelo desconhecido: {modelo}. Use um de {list(MODELOS)}")
    spec = MODELOS[modelo]

    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = [pasta / f"cena_{i:02d}.mp4" for i in range(len(roteiro.cenas))]

    inicio = time.monotonic()
    with requests.Session() as sessao:
        # menos paralelismo que nas imagens: vídeo é pesado e costuma ter fila
        with futuros.ThreadPoolExecutor(max_workers=2) as pool:
            tarefas = [
                pool.submit(_um, cena.imagem, serie, segundos_por_cena,
                            spec, caminho, sessao)
                for cena, caminho in zip(roteiro.cenas, caminhos)
            ]
            for tarefa in futuros.as_completed(tarefas):
                tarefa.result()
    espera = time.monotonic() - inicio

    total_segundos = segundos_por_cena * len(caminhos)
    dolar = total_segundos * spec["dolar_por_segundo"]
    custos.registrar(
        "clipes", "segundos", total_segundos, dolar,
        f"{len(caminhos)} clipes de {segundos_por_cena:.0f}s no {modelo} "
        f"(US$ {spec['dolar_por_segundo']}/s) — {espera:.0f}s de espera"
    )
    return caminhos
