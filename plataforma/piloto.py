"""Piloto automático das séries.

Só roda em série explicitamente ativada. Respeita assinatura, franquia e fila;
quando chega a hora, escolhe uma pauta inédita e cria exatamente um vídeo.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from . import temas, uso
from .banco import agora, inserir, um, varios

INTERVALOS = {
    "diario": timedelta(days=1),
    "tres_semana": timedelta(hours=56),
    "semanal": timedelta(days=7),
}

NOMES = {
    "diario": "Todo dia",
    "tres_semana": "3 vezes por semana",
    "semanal": "Toda semana",
}


def proxima(frequencia: str, base: datetime | None = None) -> str:
    base = base or datetime.now(timezone.utc)
    intervalo = INTERVALOS.get(frequencia, INTERVALOS["semanal"])
    return (base + intervalo).isoformat(timespec="seconds")


def configurar(con: sqlite3.Connection, serie_id: int, ativo: bool,
               frequencia: str) -> None:
    if frequencia not in INTERVALOS:
        frequencia = "semanal"
    atual = um(con, "SELECT piloto_ativo, proxima_geracao FROM series WHERE id=?",
               serie_id)
    ja_agendado = bool(atual and atual["piloto_ativo"] and atual["proxima_geracao"])
    quando = atual["proxima_geracao"] if ativo and ja_agendado else (agora() if ativo else "")
    con.execute(
        "UPDATE series SET piloto_ativo=?, frequencia=?, proxima_geracao=? WHERE id=?",
        (int(ativo), frequencia, quando, serie_id),
    )


def acionar_devidos(con: sqlite3.Connection) -> int:
    """Coloca na fila as séries vencidas. Retorna quantos vídeos agendou."""
    devidas = varios(con, """
        SELECT * FROM series
         WHERE piloto_ativo=1 AND arquivada=0
           AND proxima_geracao != '' AND proxima_geracao <= ?
         ORDER BY proxima_geracao LIMIT 5
    """, agora())
    criados = 0
    for serie in devidas:
        frequencia = serie["frequencia"]
        # Avança antes de chamar fornecedor: se ele falhar, não entra num loop
        # caro a cada dois segundos.
        con.execute("UPDATE series SET proxima_geracao=? WHERE id=?",
                    (proxima(frequencia), serie["id"]))
        pendente = um(con, """
            SELECT id FROM videos WHERE serie_id=?
             AND estado IN ('na_fila','gerando') LIMIT 1
        """, serie["id"])
        if pendente is not None:
            continue
        try:
            uso.conferir_novo_video(con, int(serie["usuario_id"]))
        except uso.Recusado:
            continue

        pauta = um(con, """
            SELECT id FROM temas WHERE serie_id=? AND estado='proposto'
             ORDER BY id LIMIT 1
        """, serie["id"])
        if pauta is None:
            ids = temas.propor(con, serie, quantas=1)
            tema_id = ids[0]
        else:
            tema_id = int(pauta["id"])
        inserir(con, """
            INSERT INTO videos (serie_id, usuario_id, tema_id, modo_musica,
                                plataforma_musica, criado_em)
            VALUES (?,?,?,?,?,?)
        """, serie["id"], serie["usuario_id"], tema_id, serie["modo_musica"],
             serie["plataforma_musica"], agora())
        criados += 1
    return criados
