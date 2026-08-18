"""Etapa 2b — cenas em VÍDEO, não em imagem estática.

A diferença de custo entre este arquivo e `imagens.py` continua sendo uma
decisão econômica importante:

    imagem estática : cobrada por megapixel   → centavos de dólar por vídeo
    vídeo gerado    : cobrado por clipe/segundo → varia muito por modelo

O FastWan atual deixa uma batida curta barata, mas Seedance e Kling ainda
podem levar um vídeo inteiro a vários dólares. Por isso o modo automático
aplica clipe só onde o movimento melhora retenção e mede cada execução.
"""
from __future__ import annotations

import concurrent.futures as futuros
import os
import time
from pathlib import Path

import requests

from .config import Serie
from .custos import Custos
from .direcao import prompt_movimento
from .roteiro import Roteiro

# Catálogo do que dá para usar. Cada fornecedor usa uma unidade de cobrança.
MODELOS: dict[str, dict] = {
    "wan": {
        # FastWan 2.2 5B: endpoint atual e muito mais barato para batidas
        # curtas. A cobrança documentada é por clipe 720p, não por segundo.
        "rota": "fal-ai/wan/v2.2-5b/text-to-video/fast-wan",
        "dolar_por_clipe": 0.025,
        "nota": "até 5s, 720p; preço por clipe",
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
    if "dolar_por_clipe" in modelo:
        # 121 quadros a 24 fps = cinco segundos. O limite do modelo é 161;
        # manter cinco segundos dá material suficiente sem arrastar a batida.
        quadros = min(121, max(17, 1 + int(round(segundos * 24))))
        corpo = {
            "prompt": f"{prompt}. {serie.estilo}",
            "negative_prompt": (
                "text, watermark, logo, scene cut, identity change, morphing, "
                "deformed hands, duplicate subject, flicker, low quality"
            ),
            "num_frames": quadros,
            "frames_per_second": 24,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "enable_prompt_expansion": True,
        }
    else:
        corpo = {
            "prompt": f"{prompt}. {serie.estilo}",
            "duration": max(5, int(round(segundos))),
            "aspect_ratio": "9:16",
            "resolution": "720p",
        }
    r = sessao.post(
        f"https://fal.run/{modelo['rota']}",
        json=corpo,
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
          modelo: str = "wan", segundos_por_cena: float = 5.0,
          indices: list[int] | None = None,
          tolerar_falhas: bool = False) -> list[Path]:
    """Gera clipes para todas as cenas ou apenas para os índices pedidos."""
    if modelo not in MODELOS:
        raise ValueError(f"modelo desconhecido: {modelo}. Use um de {list(MODELOS)}")
    spec = MODELOS[modelo]

    pasta.mkdir(parents=True, exist_ok=True)
    escolhidos = indices if indices is not None else list(range(len(roteiro.cenas)))
    caminhos = [pasta / f"cena_{i:02d}.mp4" for i in escolhidos]

    inicio = time.monotonic()
    with requests.Session() as sessao:
        # menos paralelismo que nas imagens: vídeo é pesado e costuma ter fila
        with futuros.ThreadPoolExecutor(max_workers=2) as pool:
            tarefas = {
                pool.submit(_um, prompt_movimento(roteiro, i), serie,
                            segundos_por_cena, spec, caminho, sessao): caminho
                for i, caminho in zip(escolhidos, caminhos)
            }
            concluidos: list[Path] = []
            for tarefa in futuros.as_completed(tarefas):
                try:
                    concluidos.append(tarefa.result())
                except Exception:                         # noqa: BLE001
                    if not tolerar_falhas:
                        raise
            caminhos = [p for p in caminhos if p in concluidos]
    espera = time.monotonic() - inicio

    total_segundos = segundos_por_cena * len(caminhos)
    if "dolar_por_clipe" in spec:
        dolar = len(caminhos) * spec["dolar_por_clipe"]
        preco = f"US$ {spec['dolar_por_clipe']}/clipe"
    else:
        dolar = total_segundos * spec["dolar_por_segundo"]
        preco = f"US$ {spec['dolar_por_segundo']}/s"
    if caminhos:
        custos.registrar(
            "clipes", "segundos", total_segundos, dolar,
            f"{len(caminhos)} clipes de {segundos_por_cena:.0f}s no {modelo} "
            f"({preco}) — {espera:.0f}s de espera"
        )
    return caminhos
