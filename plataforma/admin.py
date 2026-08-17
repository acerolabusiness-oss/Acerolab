"""Painel de controle — visão do que a Supabase deixou de mostrar.

Login com Google direto (sem passar pela Supabase) tirou o espelho que a
Supabase criava em "Authentication" a cada conta nova. Este módulo devolve
essa visão a partir da nossa própria fonte de verdade: o banco daqui.

Quem é admin é definido por e-mail, na variável `ADMIN_EMAILS` (separados
por vírgula) — sem tabela nem cargo novo, porque hoje é só o fundador.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Any

from .banco import um, varios
from .planos import PLANO_POR_CHAVE


def emails_admin() -> set[str]:
    bruto = os.environ.get("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in bruto.split(",") if e.strip()}


def eh_admin(usuario: sqlite3.Row | None) -> bool:
    if not usuario:
        return False
    return (usuario["email"] or "").strip().lower() in emails_admin()


def resumo(con: sqlite3.Connection) -> dict[str, Any]:
    usuarios = int(um(con, "SELECT COUNT(*) c FROM usuarios")["c"])
    series = int(um(con, "SELECT COUNT(*) c FROM series WHERE arquivada = 0")["c"])
    custo = float(um(con, "SELECT COALESCE(SUM(custo_reais), 0) c FROM videos "
                          "WHERE estado = 'pronto'")["c"])

    videos_por_estado = {r["estado"]: r["c"] for r in varios(
        con, "SELECT estado, COUNT(*) c FROM videos GROUP BY estado")}

    assinaturas_por_plano = {r["plano"]: r["c"] for r in varios(
        con, "SELECT plano, COUNT(*) c FROM assinaturas WHERE estado = 'ativa' "
             "GROUP BY plano")}
    mrr = sum(PLANO_POR_CHAVE[p].reais_mes * n
              for p, n in assinaturas_por_plano.items() if p in PLANO_POR_CHAVE)

    return {
        "usuarios": usuarios,
        "series": series,
        "videos_prontos": videos_por_estado.get("pronto", 0),
        "videos_na_fila": videos_por_estado.get("na_fila", 0) + videos_por_estado.get("gerando", 0),
        "videos_falharam": videos_por_estado.get("falhou", 0),
        "custo_reais": custo,
        "assinaturas_ativas": sum(assinaturas_por_plano.values()),
        "mrr_reais": mrr,
    }


def cadastros_por_dia(con: sqlite3.Connection, dias: int = 30) -> list[dict[str, Any]]:
    linhas = varios(con, f"""
        SELECT date(criado_em) AS dia, COUNT(*) AS c
          FROM usuarios
         WHERE criado_em >= datetime('now', '-{dias} days')
         GROUP BY dia
         ORDER BY dia
    """)
    por_dia = {r["dia"]: r["c"] for r in linhas}
    # preenche os dias sem cadastro com zero, senão o gráfico fica torto
    from datetime import datetime, timedelta, timezone
    hoje = datetime.now(timezone.utc).date()
    return [{"dia": (d := hoje - timedelta(days=i)).isoformat(),
             "c": por_dia.get(d.isoformat(), 0)}
            for i in range(dias - 1, -1, -1)]


def usuarios_com_uso(con: sqlite3.Connection) -> list[sqlite3.Row]:
    return varios(con, """
        SELECT u.id, u.email, u.nome, u.senha, u.criado_em,
               (SELECT COUNT(*) FROM series s WHERE s.usuario_id = u.id) AS n_series,
               (SELECT COUNT(*) FROM videos v
                 WHERE v.usuario_id = u.id AND v.estado = 'pronto') AS n_videos,
               (SELECT p.plano FROM assinaturas p
                 WHERE p.usuario_id = u.id AND p.estado = 'ativa'
                 ORDER BY p.criada_em DESC LIMIT 1) AS plano
          FROM usuarios u
         ORDER BY u.criado_em DESC
    """)
