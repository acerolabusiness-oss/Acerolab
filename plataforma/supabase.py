"""Supabase como provedor de identidade — só isso.

O Supabase guarda a credencial (senha ou conta do Google). Quem manda no
produto continua sendo o nosso banco: a tabela `usuarios` tem o cadastro e a
sessão é o nosso cookie. Assim o resto do sistema não precisa saber que o
Supabase existe, e trocar de provedor um dia mexe só neste arquivo.

Sem as três variáveis no `.env`, `configurado()` devolve False e a
plataforma continua no login local de sempre — nada quebra por falta de
credencial.

Fluxo do Google (PKCE, que é o recomendado para servidor):
  1. `/entrar/google`  → sorteamos um verificador, guardamos num cookie e
     mandamos a pessoa para o Supabase com o desafio derivado dele.
  2. o Google devolve a pessoa para o Supabase, que devolve para
     `/entrar/retorno` com um `code`.
  3. trocamos code + verificador por um token e lemos quem é a pessoa.

O verificador nunca trafega até o passo 3 — é o que impede alguém que
intercepte o `code` de usá-lo.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
from typing import Any

import requests

TEMPO = 20      # segundos: identidade é chamada síncrona, não pode pendurar


class Recusado(Exception):
    """Erro que pode ser mostrado ao usuário como está."""


# ───────────────────────────── configuração ──────────────────────────

def url() -> str:
    return (os.environ.get("SUPABASE_URL") or "").rstrip("/")


def anon() -> str:
    return os.environ.get("SUPABASE_ANON_KEY") or ""


def configurado() -> bool:
    return bool(url() and anon())


def _cabecalho(token: str | None = None) -> dict[str, str]:
    return {
        "apikey": anon(),
        "Authorization": f"Bearer {token or anon()}",
        "Content-Type": "application/json",
    }


# ─────────────────────────── traduzir o erro ─────────────────────────

# O Supabase responde em inglês e com jargão. O que a pessoa lê tem que ser
# português e tem que dizer o que fazer.
RECADOS: tuple[tuple[str, str], ...] = (
    ("invalid login credentials", "E-mail ou senha incorretos."),
    ("email not confirmed", "Confirme seu e-mail antes de entrar — veja sua caixa de entrada."),
    ("user already registered", "Já existe uma conta com esse e-mail."),
    ("password should be at least", "A senha precisa ter pelo menos 8 caracteres."),
    ("weak password", "Essa senha é fraca demais. Use uma combinação mais difícil."),
    ("over_email_send_rate_limit",
     "O envio de e-mails atingiu o limite. Espere alguns minutos e tente de novo."),
    ("you can only request this after", "Espere um minuto antes de tentar de novo."),
    ("rate limit", "Muitas tentativas seguidas. Espere um minuto."),
    ("unable to validate email", "Esse e-mail não parece válido."),
)


def _explodir(r: requests.Response) -> None:
    if r.status_code < 400:
        return
    try:
        corpo: dict[str, Any] = r.json()
    except ValueError:
        corpo = {}
    # O código do erro entra na busca junto com a mensagem: o limite de envio
    # de e-mail, por exemplo, só se identifica pelo `error_code`.
    cru = " ".join(str(corpo.get(c, "")) for c in
                   ("error_code", "msg", "error_description", "message", "error")) or r.text
    cru = cru.strip()[:300]
    for pedaco, recado in RECADOS:
        if pedaco in cru.lower():
            raise Recusado(recado)
    raise Recusado(f"Não deu para concluir agora. ({cru})")


def _pessoa(dados: dict[str, Any]) -> dict[str, str]:
    """Extrai só o que o produto precisa saber de quem entrou."""
    u = dados.get("user") or dados
    meta = u.get("user_metadata") or {}
    return {
        "id": str(u.get("id") or ""),
        "email": str(u.get("email") or ""),
        "nome": str(meta.get("full_name") or meta.get("name") or "").strip(),
    }


# ─────────────────────────── e-mail e senha ──────────────────────────

def cadastrar(email: str, senha: str, nome: str = "") -> dict[str, str]:
    """Cria a conta. O campo `confirmado` diz se já dá para entrar.

    Quando o projeto exige confirmação de e-mail, o Supabase responde 200 mas
    **sem** sessão — a pessoa só entra depois de clicar no link. Sem olhar
    isso, a plataforma deixava entrar no cadastro e recusava no login
    seguinte, que é o pior dos dois mundos.
    """
    r = requests.post(f"{url()}/auth/v1/signup", headers=_cabecalho(),
                      json={"email": email.strip(), "password": senha,
                            "data": {"full_name": nome.strip()}},
                      timeout=TEMPO)
    _explodir(r)
    dados = r.json()
    pessoa = _pessoa(dados)
    pessoa["confirmado"] = "sim" if dados.get("access_token") else ""
    return pessoa


def reenviar_confirmacao(email: str) -> None:
    """Manda o link de confirmação de novo. Some silenciosamente se o e-mail
    não existir — dizer isso entregaria quais contas estão cadastradas."""
    requests.post(f"{url()}/auth/v1/resend", headers=_cabecalho(),
                  json={"type": "signup", "email": email.strip()}, timeout=TEMPO)


def entrar(email: str, senha: str) -> dict[str, str]:
    r = requests.post(f"{url()}/auth/v1/token", params={"grant_type": "password"},
                      headers=_cabecalho(),
                      json={"email": email.strip(), "password": senha},
                      timeout=TEMPO)
    _explodir(r)
    return _pessoa(r.json())


def recuperar(email: str, volta_para: str) -> None:
    """Manda o e-mail de redefinição. Não diz se a conta existe — informar
    isso entregaria quais e-mails estão cadastrados."""
    requests.post(f"{url()}/auth/v1/recover", headers=_cabecalho(),
                  params={"redirect_to": volta_para},
                  json={"email": email.strip()}, timeout=TEMPO)


# ──────────────────────────────── Google ─────────────────────────────

def novo_verificador() -> str:
    return secrets.token_urlsafe(64)[:96]


def _desafio(verificador: str) -> str:
    resumo = hashlib.sha256(verificador.encode("ascii")).digest()
    return base64.urlsafe_b64encode(resumo).decode("ascii").rstrip("=")


def url_google(volta_para: str, verificador: str) -> str:
    from urllib.parse import urlencode
    parametros = urlencode({
        "provider": "google",
        "redirect_to": volta_para,
        "code_challenge": _desafio(verificador),
        "code_challenge_method": "s256",
    })
    return f"{url()}/auth/v1/authorize?{parametros}"


def trocar_codigo(codigo: str, verificador: str) -> dict[str, str]:
    r = requests.post(f"{url()}/auth/v1/token", params={"grant_type": "pkce"},
                      headers=_cabecalho(),
                      json={"auth_code": codigo, "code_verifier": verificador},
                      timeout=TEMPO)
    _explodir(r)
    return _pessoa(r.json())
