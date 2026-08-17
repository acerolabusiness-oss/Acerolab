"""Login com o Google — direto, sem passar pela Supabase.

Quando a troca do código acontecia na Supabase, a tela de escolha de conta do
Google mostrava "Prosseguir para wxsryudhtqtfinhrqzrp.supabase.co": o Google
sempre exibe o dono de verdade do `redirect_uri`, por segurança. Fazendo a
troca aqui, o dono passa a ser o nosso próprio domínio.

Sem `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` no `.env`, `configurado()`
devolve False e o botão de Google some — nada quebra por falta de credencial.
"""
from __future__ import annotations

import os
import secrets
from typing import Any
from urllib.parse import urlencode

import requests

TEMPO = 20      # segundos: identidade é chamada síncrona, não pode pendurar

AUTORIZAR = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
QUEM_E = "https://openidconnect.googleapis.com/v1/userinfo"


class Recusado(Exception):
    """Erro que pode ser mostrado ao usuário como está."""


def client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID") or ""


def client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET") or ""


def configurado() -> bool:
    return bool(client_id() and client_secret())


def novo_estado() -> str:
    return secrets.token_urlsafe(32)


def url_login(volta_para: str, estado: str) -> str:
    parametros = urlencode({
        "client_id": client_id(),
        "redirect_uri": volta_para,
        "response_type": "code",
        "scope": "openid email profile",
        "state": estado,
        "access_type": "online",
        "prompt": "select_account",
    })
    return f"{AUTORIZAR}?{parametros}"


def trocar_codigo(codigo: str, volta_para: str) -> dict[str, str]:
    r = requests.post(TOKEN, data={
        "code": codigo,
        "client_id": client_id(),
        "client_secret": client_secret(),
        "redirect_uri": volta_para,
        "grant_type": "authorization_code",
    }, timeout=TEMPO)
    if r.status_code >= 400:
        raise Recusado("Não deu para concluir o login com o Google agora.")
    token = r.json().get("access_token", "")

    r = requests.get(QUEM_E, headers={"Authorization": f"Bearer {token}"}, timeout=TEMPO)
    if r.status_code >= 400:
        raise Recusado("Não deu para concluir o login com o Google agora.")
    dados: dict[str, Any] = r.json()
    return {
        "id": str(dados.get("sub") or ""),
        "email": str(dados.get("email") or ""),
        "nome": str(dados.get("name") or "").strip(),
    }
