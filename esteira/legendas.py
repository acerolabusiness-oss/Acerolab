"""Etapa 4 — legendas, com Groq Whisper.

Transcreve a narração já gerada para obter o tempo de cada palavra. A tela
mostra blocos curtos de contexto e destaca a palavra atual — mais legível do
que fazer cada palavra aparecer sozinha.
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


def agrupar(palavras: list[Palavra], maximo: int = 4,
            duracao_maxima: float = 1.8) -> list[list[Palavra]]:
    """Agrupa fala em unidades que o olho consegue ler sem perder o ritmo."""
    blocos: list[list[Palavra]] = []
    atual: list[Palavra] = []
    for palavra in palavras:
        atual.append(palavra)
        pontua = palavra.texto.rstrip().endswith((".", "!", "?", ":", ";", ","))
        longa = atual[-1].fim - atual[0].inicio >= duracao_maxima
        if len(atual) >= maximo or pontua or longa:
            blocos.append(atual)
            atual = []
    if atual:
        blocos.append(atual)
    return blocos


def _ass_cor(cor: str) -> str:
    """#RRGGBB para o BGR usado pelo ASS."""
    valor = cor.lstrip("#")
    if len(valor) != 6:
        valor = "FFFFFF"
    return f"&H00{valor[4:6]}{valor[2:4]}{valor[0:2]}"


def _ass_cor_inline(cor: str) -> str:
    """Cor BGR para uma tag de override dentro do texto ASS."""
    valor = cor.lstrip("#")
    if len(valor) != 6:
        valor = "FFFFFF"
    return f"&H{valor[4:6]}{valor[2:4]}{valor[0:2]}&"


def escrever_ass(palavras: list[Palavra], destino: Path,
                 largura: int, altura: int,
                 cor: str = "#FFFFFF", contorno: str = "#000000",
                 caixa_alta: bool = True, divisor_contorno: int = 10) -> Path:
    """Blocos de 2–4 palavras com a palavra falada em destaque."""
    corpo = int(altura * 0.052)
    margem = int(altura * 0.22)
    base = "#FFFFFF" if cor.upper() != "#FFFFFF" else cor
    destaque = cor if cor.upper() != "#FFFFFF" else "#FF3B30"

    cabecalho = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {largura}
PlayResY: {altura}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fala,Arial Black,{corpo},{_ass_cor(base)},{_ass_cor(contorno)},&H00000000,-1,1,{max(3, corpo // max(1, divisor_contorno))},0,2,60,60,{margem},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = []
    for bloco in agrupar(palavras):
        for ativa, p in enumerate(bloco):
            partes = []
            for i, palavra in enumerate(bloco):
                trecho = palavra.texto.upper() if caixa_alta else palavra.texto
                if i == ativa:
                    partes.append(
                        f"{{\\c{_ass_cor_inline(destaque)}}}{_escapar(trecho)}"
                        f"{{\\c{_ass_cor_inline(base)}}}"
                    )
                else:
                    partes.append(_escapar(trecho))
            texto = ("{\\fscx94\\fscy94\\t(0,90,\\fscx100\\fscy100)}" +
                     " ".join(partes))
            linhas.append(
                f"Dialogue: 0,{_tempo(p.inicio)},{_tempo(max(p.fim, p.inicio + 0.08))},"
                f"Fala,,0,0,0,,{texto}"
            )

    destino.write_text(cabecalho + "\n".join(linhas) + "\n", encoding="utf-8")
    return destino
