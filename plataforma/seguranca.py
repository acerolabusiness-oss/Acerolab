"""Proteções HTTP pequenas, sem depender de um proxy específico."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

_acessos: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_trava = threading.Lock()


def _cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _limite(request: Request) -> tuple[int, int] | None:
    caminho = request.url.path
    if caminho in {"/entrar", "/cadastrar", "/esqueci", "/reenviar"}:
        return 10, 300
    if caminho.endswith("/gerar") or caminho.endswith("/pautas"):
        return 12, 60
    if caminho.startswith("/api/voz/"):
        return 30, 300
    if request.method == "POST":
        return 60, 60
    return None


def _grupo(request: Request) -> str:
    caminho = request.url.path
    if caminho.endswith("/gerar"):
        return "gerar"
    if caminho.endswith("/pautas"):
        return "pautas"
    if caminho.startswith("/api/voz/"):
        return "voz"
    return caminho


def excedeu_limite(request: Request) -> bool:
    regra = _limite(request)
    if regra is None:
        return False
    maximo, janela = regra
    agora = time.monotonic()
    chave = (_cliente(request), _grupo(request))
    with _trava:
        fila = _acessos[chave]
        while fila and fila[0] <= agora - janela:
            fila.popleft()
        if len(fila) >= maximo:
            return True
        fila.append(agora)
    return False


def mesma_origem(request: Request) -> bool:
    """Bloqueia POSTs vindos de outro site (CSRF), inclusive via Fetch Metadata."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return True
    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        return False
    origem = request.headers.get("origin")
    referencia = request.headers.get("referer")
    valor = origem or referencia
    if not valor:  # webhooks e clientes não-navegador não enviam estes headers
        return request.url.path == "/webhooks/stripe"
    permitido = os.environ.get("PUBLIC_URL", "").rstrip("/")
    esperado = urlparse(permitido).netloc if permitido else request.url.netloc
    return urlparse(valor).netloc == esperado


def resposta_limite() -> JSONResponse:
    return JSONResponse({"erro": "Muitas tentativas. Aguarde um pouco."}, status_code=429,
                        headers={"Retry-After": "60"})


HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; media-src 'self' data: blob:; "
        "font-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'"
    ),
}
