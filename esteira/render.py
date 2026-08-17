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
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path

from .config import Serie
from .legendas import Palavra

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
    """Divide a duração da narração entre as cenas, com um respiro no fim."""
    base = total / quantas
    fatias = [base] * quantas
    fatias[-1] += 0.35
    return fatias


def _clipe(indice: int, segundos: float, largura: int, altura: int) -> str:
    """Cena que já é vídeo: enquadra em 9:16 e corta na duração da fatia.

    `tpad` congela o último quadro caso o clipe seja mais curto que a fatia —
    sem isso o concat encurta o vídeo e o áudio fica sobrando no fim.
    """
    return (f"[{indice}:v]scale={largura}:{altura}:force_original_aspect_ratio=increase,"
            f"crop={largura}:{altura},fps={FPS},"
            f"tpad=stop_mode=clone:stop_duration={segundos:.3f},"
            f"trim=duration={segundos:.3f},setpts=PTS-STARTPTS,setsar=1[v{indice}]")


def _kenburns(indice: int, segundos: float, largura: int, altura: int) -> str:
    """Zoom lento alternando aproximar/afastar, para não ficar repetitivo.
    O scale gigante antes do zoompan é o truque conhecido contra o tremor."""
    quadros = max(2, int(segundos * FPS))
    passo = 0.9 / quadros
    if indice % 2 == 0:
        z = f"min(zoom+{passo:.6f},1.18)"
    else:
        z = f"if(lte(zoom,1.0),1.18,max(zoom-{passo:.6f},1.0))"
    return (f"[{indice}:v]scale={largura * 4}:-2,"
            f"zoompan=z='{z}':d={quadros}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s={largura}x{altura}:fps={FPS},setsar=1[v{indice}]")


def montar(imagens: list[Path], audio: Path,
           legenda: Path | list[tuple[Path, Palavra]] | None,
           serie: Serie, destino: Path) -> tuple[Path, float]:
    """Junta tudo num MP4 vertical. Devolve (arquivo, segundos de render).

    `legenda` aceita um .ass (quando há libass) ou a lista de PNGs por palavra.
    """
    inicio = time.monotonic()
    total = duracao(audio)
    fatias = _fatias(total, len(imagens))
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

    partes = [
        (_clipe if video else _kenburns)(i, seg, L, A)
        for i, (seg, video) in enumerate(zip(fatias, e_video))
    ]
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
