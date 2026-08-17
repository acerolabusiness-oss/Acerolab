"""Capa do vídeo — o quadro que aparece na grade.

Vídeo sem capa vira retângulo cinza, e aí a tela do produto fica com cara de
planilha. Aqui a gente tira um quadro do próprio MP4 e guarda em webp: pesa
uns 30 KB e é o que faz a página parecer o que ela é, uma prateleira de
vídeo.

Duas decisões que vieram de erro medido, não de gosto:

1. O quadro é o do segundo 1,2, não o do zero — a primeira cena costuma
   abrir escura e a capa sairia preta.
2. O ffmpeg entrega **PNG** e quem grava o webp é o Pillow. Várias builds
   de ffmpeg vêm sem libwebp (a do brew neste Mac é uma delas, a mesma que
   vem sem libass) e aí pedir webp direto falha calado.
"""
from __future__ import annotations

import shutil
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image

SEGUNDO = 1.2
LARGURA = 720          # o card mostra ~360px; o dobro cobre tela retina
QUALIDADE = 80


def gerar(video: Path, destino: Path) -> Path | None:
    """Extrai a capa. Devolve None se não der.

    Capa é enfeite: não pode derrubar um vídeo que já ficou pronto.
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not video.exists():
        return None

    processo = subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error",
         "-ss", str(SEGUNDO), "-i", str(video),
         "-frames:v", "1", "-vf", f"scale={LARGURA}:-2",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True,
    )
    if processo.returncode != 0 or not processo.stdout:
        return None

    try:
        quadro = Image.open(BytesIO(processo.stdout)).convert("RGB")
        destino.parent.mkdir(parents=True, exist_ok=True)
        quadro.save(destino, "WEBP", quality=QUALIDADE, method=6)
    except Exception:                                        # noqa: BLE001
        return None
    return destino
