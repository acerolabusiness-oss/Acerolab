"""Autoriza o uso pago e calcula a franquia mensal."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from .banco import um
from .planos import PLANO_POR_CHAVE


class Recusado(Exception):
    pass


def assinatura_ativa(con: sqlite3.Connection, usuario_id: int):
    return um(con, """
        SELECT * FROM assinaturas WHERE usuario_id=? AND estado='ativa'
         ORDER BY id DESC LIMIT 1
    """, usuario_id)


def _liberar_local() -> bool:
    return os.environ.get("ACEROLAB_ALLOW_UNPAID", "").lower() in {"1", "true", "sim"}


def exigir_assinatura(con: sqlite3.Connection, usuario_id: int):
    assinatura = assinatura_ativa(con, usuario_id)
    if assinatura is None and not _liberar_local():
        raise Recusado("Assine um plano antes de gerar vídeos.")
    return assinatura


def conferir_nova_serie(con: sqlite3.Connection, usuario_id: int) -> None:
    assinatura = exigir_assinatura(con, usuario_id)
    if assinatura is None:
        return
    usadas = int(um(con, "SELECT COUNT(*) c FROM series WHERE usuario_id=? AND arquivada=0",
                    usuario_id)["c"])
    if usadas >= int(assinatura["series"]):
        raise Recusado("Seu plano já está usando todas as séries contratadas.")


def conferir_novo_video(con: sqlite3.Connection, usuario_id: int) -> dict[str, int]:
    assinatura = exigir_assinatura(con, usuario_id)
    if assinatura is None:
        return {"usados": 0, "limite": 999999}
    plano = PLANO_POR_CHAVE.get(assinatura["plano"])
    if plano is None:
        raise Recusado("O plano ativo não é reconhecido. Fale com o suporte.")
    inicio = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00")
    # Falha não consome franquia; fila e geração contam para impedir rajadas.
    usados = int(um(con, """
        SELECT COUNT(*) c FROM videos
         WHERE usuario_id=? AND criado_em>=? AND estado!='falhou'
    """, usuario_id, inicio)["c"])
    limite = plano.videos_mes * int(assinatura["series"])
    if usados >= limite:
        raise Recusado(f"Sua franquia mensal de {limite} vídeos foi usada.")
    pendentes = int(um(con, """
        SELECT COUNT(*) c FROM videos WHERE usuario_id=? AND estado IN ('na_fila','gerando')
    """, usuario_id)["c"])
    max_fila = max(3, min(20, int(assinatura["series"]) * 3))
    if pendentes >= max_fila:
        raise Recusado(f"Você já tem {pendentes} vídeos em produção. Aguarde a fila.")
    return {"usados": usados, "limite": limite}
