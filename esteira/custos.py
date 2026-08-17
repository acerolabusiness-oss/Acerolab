"""Contabilidade da esteira.

O ponto do projeto: cada etapa registra o que realmente consumiu, e no fim
sai um custo por vídeo medido — não estimado.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .config import Precos


@dataclass
class Lancamento:
    etapa: str
    unidade: str        # "tokens", "megapixels", "caracteres", "segundos"
    quantidade: float
    dolar: float
    detalhe: str = ""


@dataclass
class Custos:
    precos: Precos = field(default_factory=Precos)
    lancamentos: list[Lancamento] = field(default_factory=list)

    def registrar(self, etapa: str, unidade: str, quantidade: float,
                  dolar: float, detalhe: str = "") -> None:
        self.lancamentos.append(
            Lancamento(etapa, unidade, round(quantidade, 4), round(dolar, 6), detalhe)
        )

    # ── cálculos por fornecedor ──

    def roteiro(self, entrada: int, saida: int) -> float:
        d = (entrada / 1_000_000 * self.precos.roteiro_entrada_por_milhao
             + saida / 1_000_000 * self.precos.roteiro_saida_por_milhao)
        self.registrar("roteiro", "tokens", entrada + saida, d,
                       f"{entrada} entrada + {saida} saída")
        return d

    def imagem(self, megapixels: float, quantas: int) -> float:
        total_mp = megapixels * quantas
        d = total_mp * self.precos.imagem_por_megapixel
        self.registrar("imagens", "megapixels", total_mp, d,
                       f"{quantas} imagens de {megapixels:.2f} MP")
        return d

    def narracao(self, caracteres: int) -> float:
        d = caracteres / 1000 * self.precos.narracao_por_mil_caracteres
        self.registrar("narração", "caracteres", caracteres, d,
                       f"{caracteres} caracteres")
        return d

    def legenda(self, segundos: float) -> float:
        d = segundos / 3600 * self.precos.legenda_por_hora
        self.registrar("legendas", "segundos", segundos, d,
                       f"{segundos:.1f}s de áudio")
        return d

    # ── totais ──

    @property
    def total_dolar(self) -> float:
        return sum(l.dolar for l in self.lancamentos)

    @property
    def total_real(self) -> float:
        return self.total_dolar * self.precos.dolar

    def relatorio(self) -> str:
        larg = max((len(l.etapa) for l in self.lancamentos), default=8)
        linhas = [f"{'etapa'.ljust(larg)}  {'USD':>10}  {'BRL':>8}  detalhe"]
        linhas.append("─" * (larg + 34))
        for l in self.lancamentos:
            linhas.append(
                f"{l.etapa.ljust(larg)}  {l.dolar:>10.5f}  "
                f"{l.dolar * self.precos.dolar:>8.4f}  {l.detalhe}"
            )
        linhas.append("─" * (larg + 34))
        linhas.append(
            f"{'TOTAL'.ljust(larg)}  {self.total_dolar:>10.5f}  {self.total_real:>8.4f}"
        )
        return "\n".join(linhas)

    def salvar(self, caminho: Path) -> None:
        caminho.write_text(json.dumps({
            "lancamentos": [asdict(l) for l in self.lancamentos],
            "total_usd": round(self.total_dolar, 6),
            "total_brl": round(self.total_real, 4),
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def consolidar(varios: list[Custos], precos: Precos) -> str:
    """Resumo de uma leva de vídeos — é este número que decide a franquia."""
    if not varios:
        return "nenhum vídeo gerado"
    totais = sorted(c.total_dolar for c in varios)
    n = len(totais)
    media = sum(totais) / n
    mediana = totais[n // 2] if n % 2 else (totais[n // 2 - 1] + totais[n // 2]) / 2

    por_etapa: dict[str, float] = {}
    for c in varios:
        for l in c.lancamentos:
            por_etapa[l.etapa] = por_etapa.get(l.etapa, 0.0) + l.dolar

    linhas = [f"\n{n} vídeos gerados", "─" * 46]
    for etapa, d in sorted(por_etapa.items(), key=lambda kv: -kv[1]):
        fatia = d / sum(por_etapa.values()) * 100
        linhas.append(f"  {etapa:<12} US$ {d / n:.5f} por vídeo   ({fatia:4.1f}% do custo)")
    linhas += [
        "─" * 46,
        f"  média    US$ {media:.5f}   R$ {media * precos.dolar:.4f}",
        f"  mediana  US$ {mediana:.5f}   R$ {mediana * precos.dolar:.4f}",
        f"  mín/máx  R$ {totais[0] * precos.dolar:.4f} / R$ {totais[-1] * precos.dolar:.4f}",
        "",
        f"  Tabela do franqueador: R$ 0,18 a R$ 0,36 por vídeo.",
        f"  Medido aqui: R$ {media * precos.dolar:.4f}.",
    ]
    return "\n".join(linhas)
