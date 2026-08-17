"""Etapa 3 — narração, com ElevenLabs.

Linha mais cara e mais imprevisível da conta: o preço por caractere muda por
plano, e o Flash cobra metade do que os modelos normais cobram. Por isso o
custo é calculado a partir dos caracteres realmente enviados.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

from .config import MODELO_NARRACAO, Serie
from .custos import Custos
from .roteiro import Roteiro

BASE = "https://api.elevenlabs.io/v1/text-to-speech"
VOZ_PADRAO = "JBFqnCBsd6RMkjVDRZzb"   # voz multilíngue neutra


def gerar(roteiro: Roteiro, serie: Serie, destino: Path, custos: Custos) -> tuple[Path, str]:
    """Narra o roteiro inteiro num áudio só, para a prosódia não picotar."""
    texto = " ".join(cena.narracao.strip() for cena in roteiro.cenas)
    voz = serie.voz or VOZ_PADRAO

    r = requests.post(
        f"{BASE}/{voz}",
        json={
            "text": texto,
            "model_id": MODELO_NARRACAO,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": 1.05},
        },
        headers={
            "xi-api-key": os.environ["ELEVENLABS_API_KEY"],
            "accept": "audio/mpeg",
        },
        timeout=180,
    )
    r.raise_for_status()

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(r.content)

    custos.narracao(len(texto))
    return destino, texto
