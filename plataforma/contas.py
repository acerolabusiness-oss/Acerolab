"""Cadastro, senha e sessão.

Sem biblioteca de autenticação: scrypt sai da stdlib e o cookie de sessão é
só um token aleatório apontando para uma linha do banco. Menos dependência,
e nada de segredo de assinatura para vazar.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .banco import agora, inserir, um

COOKIE = "acerolab_sessao"
DIAS_DE_SESSAO = 30

# Parâmetros do scrypt. n=2**14 leva ~50ms neste Mac: incômodo para quem
# tenta força bruta, imperceptível para quem está entrando.
_N, _R, _P = 2 ** 14, 8, 1

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class Recusado(Exception):
    """Erro que pode ser mostrado ao usuário como está."""


# ───────────────────────────── senha ─────────────────────────────

def cifrar(senha: str) -> str:
    sal = os.urandom(16)
    bruto = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return f"{sal.hex()}${bruto.hex()}"


def confere(senha: str, guardado: str) -> bool:
    try:
        sal_hex, esperado = guardado.split("$", 1)
        sal = bytes.fromhex(sal_hex)
    except ValueError:
        return False
    bruto = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return hmac.compare_digest(bruto.hex(), esperado)


def validar(email: str, senha: str) -> None:
    if not EMAIL.match(email.strip()):
        raise Recusado("Esse e-mail não parece válido.")
    if len(senha) < 8:
        raise Recusado("A senha precisa ter pelo menos 8 caracteres.")


# ──────────────────────────── usuários ───────────────────────────

def cadastrar(con: sqlite3.Connection, email: str, senha: str, nome: str = "") -> int:
    email = email.strip()
    validar(email, senha)
    if um(con, "SELECT id FROM usuarios WHERE email = ?", email):
        raise Recusado("Já existe uma conta com esse e-mail.")
    return inserir(
        con,
        "INSERT INTO usuarios (email, senha, nome, criado_em) VALUES (?,?,?,?)",
        email, cifrar(senha), nome.strip(), agora(),
    )


def vincular(con: sqlite3.Connection, pessoa: dict[str, str]) -> int:
    """Casa quem veio do provedor com o cadastro daqui, pelo e-mail.

    Se a pessoa já tinha conta por senha e agora entrou pelo Google, o mesmo
    e-mail leva ao mesmo cadastro — em vez de criar uma conta paralela que
    não enxerga as séries dela.
    """
    email = (pessoa.get("email") or "").strip()
    if not email:
        raise Recusado("O provedor não devolveu um e-mail. Tente por e-mail e senha.")

    linha = um(con, "SELECT id, nome, supabase_id FROM usuarios WHERE email = ?", email)
    if linha:
        if pessoa.get("id") and not linha["supabase_id"]:
            con.execute("UPDATE usuarios SET supabase_id = ? WHERE id = ?",
                        (pessoa["id"], linha["id"]))
        if pessoa.get("nome") and not linha["nome"]:
            con.execute("UPDATE usuarios SET nome = ? WHERE id = ?",
                        (pessoa["nome"], linha["id"]))
        return int(linha["id"])

    return inserir(
        con,
        """INSERT INTO usuarios (email, senha, nome, supabase_id, criado_em)
           VALUES (?,'',?,?,?)""",
        email, pessoa.get("nome", ""), pessoa.get("id", ""), agora(),
    )


def autenticar(con: sqlite3.Connection, email: str, senha: str) -> int:
    linha = um(con, "SELECT id, senha FROM usuarios WHERE email = ?", email.strip())
    if linha and not linha["senha"]:
        # Conta criada pelo Google não tem senha aqui; dizer isso evita a
        # pessoa ficar tentando lembrar uma senha que nunca existiu.
        raise Recusado("Essa conta entra pelo Google. Use o botão “Continuar com o Google”.")
    if not linha or not confere(senha, linha["senha"]):
        # Mensagem única de propósito: dizer qual dos dois errou entrega
        # quais e-mails existem na base.
        raise Recusado("E-mail ou senha incorretos.")
    return int(linha["id"])


# ──────────────────────────── sessões ────────────────────────────

def abrir_sessao(con: sqlite3.Connection, usuario_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(days=DIAS_DE_SESSAO)
    con.execute(
        "INSERT INTO sessoes (token, usuario_id, criada_em, expira_em) VALUES (?,?,?,?)",
        (token, usuario_id, agora(), expira.isoformat(timespec="seconds")),
    )
    return token


def fechar_sessao(con: sqlite3.Connection, token: str) -> None:
    con.execute("DELETE FROM sessoes WHERE token = ?", (token,))


def usuario_da_sessao(con: sqlite3.Connection, token: str | None) -> sqlite3.Row | None:
    if not token:
        return None
    linha = um(con, """
        SELECT u.id, u.email, u.nome, s.expira_em
          FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
         WHERE s.token = ?
    """, token)
    if not linha:
        return None
    if linha["expira_em"] < agora():
        fechar_sessao(con, token)
        return None
    return linha


def limpar_expiradas(con: sqlite3.Connection) -> None:
    con.execute("DELETE FROM sessoes WHERE expira_em < ?", (agora(),))
