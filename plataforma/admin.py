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


def fila_saude(con: sqlite3.Connection) -> dict[str, Any]:
    """Estado da esteira de geração: o que está parado, o que falha, o que custa."""
    r = um(con, """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN estado IN ('na_fila','gerando') THEN 1 ELSE 0 END) AS na_fila,
            SUM(CASE WHEN estado = 'falhou' THEN 1 ELSE 0 END) AS falharam,
            SUM(CASE WHEN estado = 'pronto' THEN 1 ELSE 0 END) AS prontos,
            AVG(CASE WHEN estado = 'pronto' THEN custo_reais END) AS custo_medio,
            AVG(CASE WHEN estado = 'pronto' AND terminado_em != ''
                     THEN (julianday(terminado_em) - julianday(criado_em)) * 86400 END)
                AS segundos_medios
          FROM videos
    """)
    total = r["total"] or 0
    falharam = r["falharam"] or 0
    return {
        "total": total,
        "na_fila": r["na_fila"] or 0,
        "falharam": falharam,
        "prontos": r["prontos"] or 0,
        "taxa_falha": (falharam / total) if total else 0.0,
        "custo_medio": r["custo_medio"] or 0.0,
        "segundos_medios": r["segundos_medios"] or 0.0,
    }


def erros_recentes(con: sqlite3.Connection, limite: int = 10) -> list[sqlite3.Row]:
    return varios(con, """
        SELECT v.id, v.titulo, v.erro, v.criado_em, u.email
          FROM videos v JOIN usuarios u ON u.id = v.usuario_id
         WHERE v.estado = 'falhou' AND v.erro != ''
         ORDER BY v.criado_em DESC
         LIMIT ?
    """, limite)


def assinaturas_resumo(con: sqlite3.Connection) -> dict[str, Any]:
    """Distribuição por plano/estado e novas assinaturas por mês — sem inventar
    histórico de MRR que o banco não guarda (não há data de cancelamento)."""
    por_plano_estado = varios(con, """
        SELECT plano, estado, COUNT(*) AS c
          FROM assinaturas
         GROUP BY plano, estado
         ORDER BY plano
    """)
    novas_por_mes = varios(con, """
        SELECT strftime('%Y-%m', criada_em) AS mes, COUNT(*) AS c
          FROM assinaturas
         GROUP BY mes
         ORDER BY mes
    """)
    return {
        "por_plano_estado": [dict(r) for r in por_plano_estado],
        "novas_por_mes": [dict(r) for r in novas_por_mes],
    }


def usuario_detalhe(con: sqlite3.Connection, usuario_id: int) -> dict[str, Any] | None:
    """`pessoa`, não `usuario`: esse nome é reservado para quem está logado
    (a barra lateral em base.html lê `usuario` do contexto) — usar o mesmo
    nome aqui faria a tela de um cliente qualquer roubar a sessão do admin
    no template."""
    pessoa = um(con, "SELECT * FROM usuarios WHERE id = ?", usuario_id)
    if pessoa is None:
        return None
    series = varios(con, """
        SELECT s.*,
               (SELECT COUNT(*) FROM videos v
                 WHERE v.serie_id = s.id AND v.estado = 'pronto') AS n_videos,
               (SELECT COUNT(*) FROM temas t
                 WHERE t.serie_id = s.id AND t.estado = 'proposto') AS n_pautas
          FROM series s
         WHERE s.usuario_id = ?
         ORDER BY s.criada_em DESC
    """, usuario_id)
    videos = varios(con, """
        SELECT v.*, s.nome AS serie_nome
          FROM videos v JOIN series s ON s.id = v.serie_id
         WHERE v.usuario_id = ?
         ORDER BY v.criado_em DESC
         LIMIT 50
    """, usuario_id)
    assinaturas = varios(con, """
        SELECT * FROM assinaturas WHERE usuario_id = ? ORDER BY criada_em DESC
    """, usuario_id)
    return {"pessoa": pessoa, "series": series, "videos": videos, "assinaturas": assinaturas}
