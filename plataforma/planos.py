"""Os planos da ACEROLAB, num lugar só.

**Estes preços ainda são os do AutoShortz.** Ficam aqui como ponto de
partida porque é o modelo que você está seguindo, mas a análise de margem
diz que eles precisam de decisão sua antes de virarem cobrança de verdade:

    plano    receita   vídeos/mês   teto de custo por vídeo
    Inicial  R$ 19,90      13              R$ 1,00
    Diário   R$ 29,90      30              R$ 0,65
    Pro      R$ 49,90      60              R$ 0,54
    Ultra    R$ 69,90      90              R$ 0,50   ← e R$ 0,38 no anual

O teto já desconta os 20% de royalty, ~5% de gateway e ~10% de imposto. Se
o custo medido por vídeo ficar acima do teto, aquele plano dá prejuízo — e
quanto mais vender, maior o prejuízo. O número que manda é o do Ultra.

Preço é em CENTAVOS, inteiro. Ponto flutuante em dinheiro erra centavo na
soma, e centavo errado em cobrança recorrente vira reclamação.
"""
from __future__ import annotations

from dataclasses import dataclass

MOEDA = "brl"
DESCONTO_ANUAL = 0.25          # "economize 25%" — 12 meses pelo preço de 9


@dataclass(frozen=True)
class Plano:
    chave: str
    nome: str
    ritmo: str                 # como o cliente entende
    videos_mes: int            # o que a gente precisa produzir
    centavos_mes: int
    destaque: str = ""

    @property
    def reais_mes(self) -> float:
        return self.centavos_mes / 100

    @property
    def centavos_ano(self) -> int:
        """12 meses com o desconto, arredondado para centavo inteiro."""
        return round(self.centavos_mes * 12 * (1 - DESCONTO_ANUAL))

    @property
    def por_video(self) -> float:
        return self.reais_mes / self.videos_mes

    def teto_de_custo(self, royalty: float = 0.20, gateway: float = 0.05,
                      imposto: float = 0.10, anual: bool = False) -> float:
        """Quanto pode custar cada vídeo para este plano não dar prejuízo."""
        receita = (self.centavos_ano / 12 if anual else self.centavos_mes) / 100
        return receita * (1 - royalty - gateway - imposto) / self.videos_mes


PLANOS: tuple[Plano, ...] = (
    Plano("inicial", "Inicial", "3 vídeos por semana", 13, 1990),
    Plano("diario",  "Diário",  "1 vídeo por dia",     30, 2990),
    Plano("pro",     "Pro",     "2 vídeos por dia",    60, 4990, "Mais popular"),
    Plano("ultra",   "Ultra",   "3 vídeos por dia",    90, 6990, "Melhor custo"),
)

PLANO_POR_CHAVE = {p.chave: p for p in PLANOS}

# O que todo plano entrega. Fica aqui para a tela de preços e o e-mail de
# boas-vindas não contarem histórias diferentes.
INCLUSO: tuple[str, ...] = (
    "Roteiro, narração, imagens e legendas gerados por IA",
    "A série propõe os temas — você aprova antes de gastar",
    "9 estilos visuais e 4 estilos de legenda",
    "7 idiomas e 6 vozes",
    "Música de fundo sorteada a cada vídeo",
    "Sem marca d'água",
    "Vídeo que falha não conta no seu plano",
)


def relatorio_de_margem(custo_por_video: float, royalty: float = 0.20) -> str:
    """Tabela de margem para um custo por vídeo medido. Serve de checagem
    rápida antes de mexer em preço."""
    linhas = [f"custo medido: R$ {custo_por_video:.2f} por vídeo   royalty: {royalty:.0%}",
              "",
              f"{'plano':<10}{'receita':>10}{'custo':>10}{'royalty':>10}{'sobra':>10}"]
    for p in PLANOS:
        receita = p.reais_mes
        custo = custo_por_video * p.videos_mes
        r = receita * royalty
        sobra = receita - custo - r
        marca = "  <-- prejuízo" if sobra < 0 else ""
        linhas.append(f"{p.nome:<10}{receita:>10.2f}{custo:>10.2f}{r:>10.2f}"
                      f"{sobra:>10.2f}{marca}")
    return "\n".join(linhas)
