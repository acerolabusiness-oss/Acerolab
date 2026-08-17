"""Etapa 4 — legendas, com Groq Whisper.

Transcreve a narração já gerada para obter o tempo de cada PALAVRA. É esse
carimbo por palavra que permite a legenda estilo TikTok, uma palavra por vez.
Custa quase nada (US$ 0,04 por hora de áudio).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import MODELO_LEGENDA
from .custos import Custos

ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"


@dataclass
class Palavra:
    texto: str
    inicio: float
    fim: float


def transcrever(audio: Path, idioma: str, custos: Custos) -> list[Palavra]:
    with audio.open("rb") as arquivo:
        r = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            files={"file": (audio.name, arquivo, "audio/mpeg")},
            data={
                "model": MODELO_LEGENDA,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "word",
                "language": idioma.split("-")[0],
            },
            timeout=180,
        )
    r.raise_for_status()
    dados = r.json()

    palavras = [
        Palavra(p["word"].strip(), float(p["start"]), float(p["end"]))
        for p in dados.get("words", []) if p["word"].strip()
    ]
    custos.legenda(float(dados.get("duration", 0.0)))
    return palavras


def _escapar(texto: str) -> str:
    """ASS trata \\ { } como controle; vírgula separa campos do diálogo."""
    return texto.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _tempo(segundos: float) -> str:
    centesimos = int(round(segundos * 100))
    h, resto = divmod(centesimos, 360000)
    m, resto = divmod(resto, 6000)
    s, cs = divmod(resto, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def escrever_ass(palavras: list[Palavra], destino: Path,
                 largura: int, altura: int) -> Path:
    """Legenda palavra a palavra, no formato ASS (o ffmpeg queima direto)."""
    corpo = int(altura * 0.055)
    margem = int(altura * 0.22)

    cabecalho = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fala,Arial Black,{corpo},&H00FFFFFF,&H00000000,&H00000000,-1,1,{max(3, corpo // 12)},0,2,60,60,{margem},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = []
    for p in palavras:
        # um leve "pop" na entrada dá o ritmo do formato
        texto = "{\\fscx88\\fscy88\\t(0,90,\\fscx104\\fscy104)\\t(90,150,\\fscx100\\fscy100)}" \
                + _escapar(p.texto.upper())
        linhas.append(
            f"Dialogue: 0,{_tempo(p.inicio)},{_tempo(max(p.fim, p.inicio + 0.08))},"
            f"Fala,,0,0,0,,{texto}"
        )

    destino.write_text(cabecalho + "\n".join(linhas) + "\n", encoding="utf-8")
    return destino
