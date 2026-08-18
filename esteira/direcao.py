"""Decisões do diretor automático.

O piloto não transforma tudo em clipe só porque a API permite. Movimento é
reservado para o gancho, a virada, o final e os picos de energia; nos respiros,
uma imagem bem dirigida com câmera virtual dá mais clareza e custa menos.
"""
from __future__ import annotations

from .roteiro import Roteiro


def cenas_com_movimento(roteiro: Roteiro, proporcao: float = 0.40) -> list[int]:
    """Escolhe os índices que merecem vídeo, preservando ritmo e orçamento."""
    total = len(roteiro.cenas)
    if total == 0:
        return []
    alvo = min(total, max(2, round(total * proporcao)))
    prioridade = sorted(
        range(total),
        key=lambda i: (
            roteiro.cenas[i].papel in {"gancho", "virada", "final"},
            roteiro.cenas[i].energia,
            -i,
        ),
        reverse=True,
    )
    escolhidas = set(prioridade[:alvo])
    escolhidas.add(0)
    if total > 1:
        escolhidas.add(total - 1)

    # Dois clipes adjacentes longos parecem uma única cena. Quando dá, troca
    # o menos importante por outra batida para criar contraste.
    resultado = sorted(escolhidas)
    if len(resultado) > 2:
        for indice in list(resultado):
            if indice - 1 not in escolhidas:
                continue
            alternativa = next(
                (i for i in prioridade if i not in escolhidas and i - 1 not in escolhidas),
                None,
            )
            if alternativa is not None and roteiro.cenas[indice].papel not in {"gancho", "final"}:
                escolhidas.remove(indice)
                escolhidas.add(alternativa)
    return sorted(escolhidas)


def prompt_movimento(roteiro: Roteiro, indice: int) -> str:
    cena = roteiro.cenas[indice]
    return (
        f"{cena.imagem}. Motion direction: {cena.movimento}. "
        "Keep subject identity, wardrobe, environment and color palette consistent. "
        "One continuous shot, physically plausible motion, no scene transition."
    )
