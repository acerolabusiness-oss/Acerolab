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

# Um bloqueio momentâneo (franquia, assinatura ou fornecedor) não deve jogar a
# próxima tentativa para a semana seguinte. Também não convém consultar o banco
# a cada dois segundos enquanto nada pode ser feito.
REPETIR_BLOQUEIO = timedelta(minutes=30)
REPETIR_FALHA = timedelta(minutes=10)

NOMES = {
    "diario": "Todo dia",
    "tres_semana": "3 vezes por semana",
    "semanal": "Toda semana",
}


def proxima(frequencia: str, base: datetime | None = None) -> str:
    base = base or datetime.now(timezone.utc)
    intervalo = INTERVALOS.get(frequencia, INTERVALOS["semanal"])
    return (base + intervalo).isoformat(timespec="seconds")


def proxima_cadencia(frequencia: str, prevista: str,
                     base: datetime | None = None) -> str:
    """Avança a partir do horário planejado, sem acumular atraso nem deriva.

    Somar sempre a partir de ``agora`` faz uma série diária andar alguns
    minutos para a frente a cada execução. Aqui mantemos o horário original e,
    se o servidor ficou fora do ar, pulamos somente os ciclos já vencidos.
    """
    base = base or datetime.now(timezone.utc)
    intervalo = INTERVALOS.get(frequencia, INTERVALOS["semanal"])
    try:
        marcada = datetime.fromisoformat(prevista)
        if marcada.tzinfo is None:
            marcada = marcada.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        marcada = base
    seguinte = marcada + intervalo
    while seguinte <= base:
        seguinte += intervalo
    return seguinte.isoformat(timespec="seconds")


def _repetir_em(espera: timedelta) -> str:
    return (datetime.now(timezone.utc) + espera).isoformat(timespec="seconds")


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
        pendente = um(con, """
            SELECT id FROM videos WHERE serie_id=?
             AND estado IN ('na_fila','gerando') LIMIT 1
        """, serie["id"])
        if pendente is not None:
            # O ciclo continua vencido. Assim que o vídeo atual terminar, o
            # piloto volta e cria o próximo sem perder a programação.
            continue
        try:
            uso.conferir_novo_video(con, int(serie["usuario_id"]))
        except uso.Recusado:
            con.execute("UPDATE series SET proxima_geracao=? WHERE id=?",
                        (_repetir_em(REPETIR_BLOQUEIO), serie["id"]))
            continue

        # Tema, vídeo e relógio formam uma única operação. Se a sugestão de
        # pauta falhar, nada fica pela metade e o ciclo é tentado novamente em
        # poucos minutos — não somente na próxima semana.
        con.execute("SAVEPOINT ciclo_piloto")
        try:
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
            """, serie["id"], serie["usuario_id"], tema_id,
                 serie["modo_musica"], serie["plataforma_musica"], agora())
            con.execute("UPDATE series SET proxima_geracao=? WHERE id=?", (
                proxima_cadencia(frequencia, serie["proxima_geracao"]),
                serie["id"],
            ))
            con.execute("RELEASE SAVEPOINT ciclo_piloto")
            criados += 1
        except Exception as erro:  # noqa: BLE001 - um ciclo não trava os demais
            con.execute("ROLLBACK TO SAVEPOINT ciclo_piloto")
            con.execute("RELEASE SAVEPOINT ciclo_piloto")
            con.execute("UPDATE series SET proxima_geracao=? WHERE id=?",
                        (_repetir_em(REPETIR_FALHA), serie["id"]))
            print(f"[piloto] série {serie['id']} será tentada novamente: {erro}")
    return criados
