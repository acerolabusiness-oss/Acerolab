"""Etapa 5 — montagem em MP4, com ffmpeg.

Esta etapa não aparece na tabela de custos do franqueador, mas existe: é
tempo de CPU, e num servidor isso é dinheiro. O tempo de render é medido e
sai no relatório para ninguém esquecer dele de novo.

Legenda: usa `subtitles` (libass) quando a build tem, e cai para sobreposição
de PNG quando não tem. Várias builds de ffmpeg — inclusive a do brew no Mac —
vêm sem libass, e aí `subtitles` e `drawtext` nem existem.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from .config import Serie
from .legendas import Palavra
from .roteiro import Roteiro

FPS = 30


def _ffmpeg() -> str:
    caminho = shutil.which("ffmpeg")
    if not caminho:
        raise RuntimeError("ffmpeg não encontrado no PATH")
    return caminho


@lru_cache(maxsize=1)
def tem_libass() -> bool:
    """A build tem o filtro `subtitles`?"""
    saida = subprocess.run([_ffmpeg(), "-hide_banner", "-filters"],
                           capture_output=True, text=True)
    return any(linha.split()[1:2] == ["subtitles"]
               for linha in saida.stdout.splitlines() if linha.strip())


def duracao(midia: Path) -> float:
    saida = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error",
         "-show_entries", "format=duration", "-of", "json", str(midia)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(saida.stdout)["format"]["duration"])


def _fatias(total: float, quantas: int) -> list[float]:
    """Fallback: divide a duração quando ainda não há marcação da fala."""
    if quantas <= 0:
        return []
    base = total / quantas
    fatias = [base] * quantas
    return fatias


def fatias_por_fala(roteiro: Roteiro, palavras: list[Palavra],
                    total: float) -> list[float]:
    """Alinha a troca de cena à narração escrita e aos timestamps reais."""
    if not roteiro.cenas or not palavras:
        return _fatias(total, len(roteiro.cenas))
    pesos = [max(1, len(re.findall(r"\w+", c.narracao, flags=re.UNICODE)))
             for c in roteiro.cenas]
    soma = sum(pesos)
    limites = [0.0]
    acumulado = 0
    for peso in pesos[:-1]:
        acumulado += peso
        indice = min(len(palavras) - 1,
                     max(1, round(acumulado / soma * len(palavras))))
        anterior = palavras[indice - 1]
        proxima = palavras[indice]
        limites.append((anterior.fim + proxima.inicio) / 2)
    limites.append(total)
    fatias = [max(0.25, limites[i + 1] - limites[i])
              for i in range(len(roteiro.cenas))]
    escala = total / sum(fatias)
    return [fatia * escala for fatia in fatias]


def _clipe(indice: int, segundos: float, largura: int, altura: int,
           origem: float) -> str:
    """Enquadra e retima o clipe até a fala; nunca congela o último quadro."""
    velocidade = segundos / max(0.1, origem)
    return (f"[{indice}:v]scale={largura}:{altura}:force_original_aspect_ratio=increase,"
            f"crop={largura}:{altura},trim=duration={origem:.3f},"
            f"setpts={velocidade:.6f}*(PTS-STARTPTS),fps={FPS},"
            f"trim=duration={segundos:.3f},setsar=1[v{indice}]")


def _kenburns(indice: int, segundos: float, largura: int, altura: int,
              movimento: str = "", energia: int = 3) -> str:
    """Câmera virtual guiada pela direção da cena, não um zoom repetido."""
    quadros = max(2, int(segundos * FPS))
    alvo = min(1.19, 1.08 + max(1, min(5, energia)) * 0.018)
    passo = (alvo - 1.0) / quadros
    if indice % 2 == 0:
        z = f"min(zoom+{passo:.6f},{alvo:.3f})"
    else:
        z = f"if(lte(zoom,1.0),{alvo:.3f},max(zoom-{passo:.6f},1.0))"
    direcao = movimento.lower()
    progresso = f"on/{max(1, quadros - 1)}"
    x = "iw/2-(iw/zoom/2)"
    y = "ih/2-(ih/zoom/2)"
    if "pan right" in direcao or "left to right" in direcao:
        x = f"(iw-iw/zoom)*{progresso}"
    elif "pan left" in direcao or "right to left" in direcao:
        x = f"(iw-iw/zoom)*(1-{progresso})"
    elif "tilt up" in direcao or "rises" in direcao:
        y = f"(ih-ih/zoom)*(1-{progresso})"
    elif "tilt down" in direcao or "descends" in direcao:
        y = f"(ih-ih/zoom)*{progresso}"
    return (f"[{indice}:v]scale={largura * 4}:-2,"
            f"zoompan=z='{z}':d={quadros}:"
            f"x='{x}':y='{y}':"
            f"s={largura}x{altura}:fps={FPS},setsar=1[v{indice}]")


def montar(imagens: list[Path], audio: Path,
           legenda: Path | list[tuple[Path, Palavra]] | None,
           serie: Serie, destino: Path,
           roteiro: Roteiro | None = None,
           palavras: list[Palavra] | None = None) -> tuple[Path, float]:
    """Junta tudo num MP4 vertical. Devolve (arquivo, segundos de render).

    `legenda` aceita um .ass (quando há libass) ou a lista de PNGs por palavra.
    """
    inicio = time.monotonic()
    total = duracao(audio)
    fatias = (fatias_por_fala(roteiro, palavras, total)
              if roteiro is not None and palavras else _fatias(total, len(imagens)))
    L, A = serie.largura, serie.altura

    # Cena pode ser imagem estática (precisa de -loop) ou clipe de vídeo.
    e_video = [c.suffix.lower() in {".mp4", ".mov", ".webm"} for c in imagens]

    cmd: list[str] = [_ffmpeg(), "-y", "-loglevel", "error"]
    for cena, seg, video in zip(imagens, fatias, e_video):
        if video:
            cmd += ["-i", str(cena)]
        else:
            # UM quadro só. O zoompan emite `d` quadros POR quadro de entrada:
            # com `-loop 1 -t`, entravam ~25 por segundo e ele multiplicava,
            # deixando a cena 0 com mais de 15 minutos. Como o `-shortest`
            # corta na duração do áudio, o vídeo inteiro cabia dentro da
            # primeira cena e as demais nunca apareciam — geradas, pagas e
            # descartadas. Com um quadro, `d` já é a duração exata da fatia.
            cmd += ["-i", str(cena)]

    i_audio = len(imagens)
    cmd += ["-i", str(audio)]
    if serie.musica_fundo:
        cmd += ["-i", str(serie.musica_fundo)]

    # os PNGs entram depois do áudio para não deslocar os índices dele
    palavras_png: list[tuple[Path, Palavra]] = []
    if isinstance(legenda, list):
        palavras_png = legenda
        for caminho, _ in palavras_png:
            cmd += ["-i", str(caminho)]

    partes = []
    for i, (cena, seg, video) in enumerate(zip(imagens, fatias, e_video)):
        if video:
            partes.append(_clipe(i, seg, L, A, duracao(cena)))
        else:
            movimento = roteiro.cenas[i].movimento if roteiro else ""
            energia = roteiro.cenas[i].energia if roteiro else 3
            partes.append(_kenburns(i, seg, L, A, movimento, energia))
    entradas = "".join(f"[v{i}]" for i in range(len(imagens)))
    partes.append(f"{entradas}concat=n={len(imagens)}:v=1:a=0[vcat]")

    atual = "vcat"
    if isinstance(legenda, Path) and legenda.exists():
        # Precisa ser subtitles=filename='...' — só `subtitles='...'` o ffmpeg
        # lê como opção sem nome e recusa. Dentro das aspas o ':' passa normal.
        seguro = str(legenda).replace("\\", "/").replace("'", r"\'")
        partes.append(f"[{atual}]subtitles=filename='{seguro}'[vout]")
        atual = "vout"
    elif palavras_png:
        base = i_audio + (2 if serie.musica_fundo else 1)
        for n, (_, palavra) in enumerate(palavras_png):
            # O piso de 80ms existe para palavra curta não piscar. Mas ele não
            # pode invadir a palavra seguinte: como cada PNG entra por overlay
            # próprio, duas janelas sobrepostas desenham as duas ao mesmo
            # tempo, uma por cima da outra. Trava no começo da próxima.
            fim = max(palavra.fim, palavra.inicio + 0.08)
            if n + 1 < len(palavras_png):
                proxima = palavras_png[n + 1][1].inicio
                fim = min(fim, max(proxima, palavra.inicio + 0.02))
            saida = "vout" if n == len(palavras_png) - 1 else f"leg{n}"
            partes.append(
                f"[{atual}][{base + n}:v]overlay=0:0:"
                f"enable='between(t,{palavra.inicio:.3f},{fim:.3f})'[{saida}]"
            )
            atual = saida
    else:
        partes.append(f"[{atual}]null[vout]")
        atual = "vout"

    if serie.musica_fundo:
        partes.append(
            f"[{i_audio + 1}:a]volume=0.10,"
            f"afade=t=out:st={max(0.0, total - 1.5):.2f}:d=1.5[bg]"
        )
        partes.append(f"[{i_audio}:a][bg]amix=inputs=2:duration=first:"
                      f"dropout_transition=0[aout]")
        mapa_audio = "[aout]"
    else:
        mapa_audio = f"{i_audio}:a"

    cmd += [
        "-filter_complex", ";".join(partes),
        "-map", f"[{atual}]", "-map", mapa_audio,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        str(destino),
    ]

    processo = subprocess.run(cmd, capture_output=True, text=True)
    if processo.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou:\n{processo.stderr[-2000:]}")

    return destino, time.monotonic() - inicio
