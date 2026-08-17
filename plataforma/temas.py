"""A série propõe temas; o cliente escolhe qual vira vídeo.

Duas das lacunas da ficha técnica moram aqui:

  · **Prévia antes de gerar.** O cliente lê o título e o gancho antes de a
    gente gastar imagem e narração. Roteiro é texto e custa centavos;
    imagem e voz é que custam. Quem não quis o tema não gerou custo.

  · **Memória da série.** Os temas já propostos entram no pedido como lista
    do que NÃO repetir. Nenhum dos dois concorrentes faz isso, e série de
    canal dark vive de não se repetir.
"""
from __future__ import annotations

import sqlite3

import anthropic
from pydantic import BaseModel, Field

from esteira.config import MODELO_ROTEIRO
from esteira.custos import Custos

from .banco import agora, inserir, varios

INSTRUCAO = """\
Você é o pauteiro de um canal de vídeo curto vertical.

Propõe pautas, não roteiros. Para cada pauta:
- O título é o que aparece na publicação: concreto, específico, sem
  reticências e sem promessa vaga. Nada de "você não vai acreditar".
- O gancho é a primeira frase da narração — os 3 segundos que decidem se a
  pessoa fica. Comece pelo fato mais surpreendente, nunca por saudação.
- Prefira o ângulo específico ao panorâmico: um caso, uma data, um número.
"""


class Pauta(BaseModel):
    titulo: str = Field(description="Título da publicação, específico e concreto.")
    gancho: str = Field(description="Primeira frase da narração, em uma linha.")


class Pautas(BaseModel):
    pautas: list[Pauta]


def _ja_usados(con: sqlite3.Connection, serie_id: int, limite: int = 60) -> list[str]:
    linhas = varios(con, """
        SELECT titulo FROM temas
         WHERE serie_id = ? ORDER BY id DESC LIMIT ?
    """, serie_id, limite)
    return [l["titulo"] for l in linhas]


def propor(con: sqlite3.Connection, serie: sqlite3.Row, quantas: int = 3) -> list[int]:
    """Gera pautas novas para a série e devolve os ids criados."""
    anteriores = _ja_usados(con, int(serie["id"]))
    evitar = ""
    if anteriores:
        lista = "\n".join(f"- {t}" for t in anteriores[:40])
        evitar = (f"\n\nA série já propôs os temas abaixo. Não repita nenhum "
                  f"deles, nem variação próxima:\n{lista}")

    cliente = anthropic.Anthropic()
    resposta = cliente.messages.parse(
        model=MODELO_ROTEIRO,
        max_tokens=2000,
        system=INSTRUCAO,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        messages=[{
            "role": "user",
            "content": (
                f"Proponha {quantas} pautas em {serie['idioma']} para uma série "
                f"sobre: {serie['nicho_texto']}.{evitar}"
            ),
        }],
        output_format=Pautas,
    )

    # O custo da pauta é real, mesmo sendo pequeno: fica registrado para
    # entrar na conta de custo por vídeo em vez de sumir no meio.
    custos = Custos()
    custos.roteiro(resposta.usage.input_tokens, resposta.usage.output_tokens)

    pautas = resposta.parsed_output
    if pautas is None:
        raise RuntimeError(f"pautas não vieram no formato esperado ({resposta.stop_reason})")

    ids: list[int] = []
    for p in pautas.pautas:
        ids.append(inserir(con, """
            INSERT INTO temas (serie_id, titulo, gancho, estado, criado_em)
            VALUES (?,?,?,'proposto',?)
        """, int(serie["id"]), p.titulo.strip(), p.gancho.strip(), agora()))
    return ids
