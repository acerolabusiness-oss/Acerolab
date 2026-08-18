"""Configuração da esteira e tabela de preços.

Todo preço fica aqui, num lugar só. Quando um fornecedor reajustar, muda-se
uma linha e o relatório de custo volta a bater.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _env(chave: str, padrao: str | None = None) -> str | None:
    return os.environ.get(chave, padrao)


def carregar_env(caminho: Path | None = None) -> None:
    """Lê um .env simples. Evita dependência extra só para isso."""
    caminho = caminho or (RAIZ / ".env")
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


# O diretório persistente também pode vir do .env. Ele precisa ser resolvido
# depois da leitura, antes de banco e fila importarem estas constantes.
carregar_env()
DATA_DIR = Path(os.environ.get("ACEROLAB_DATA_DIR") or str(RAIZ)).expanduser().resolve()
SAIDA = DATA_DIR / "saida"


# ─────────────────────────── preços ───────────────────────────

@dataclass(frozen=True)
class Precos:
    """Preços de tabela dos fornecedores, em dólar."""

    # Claude Sonnet 5 — https://platform.claude.com/docs/en/pricing
    # (promocional de US$ 2/10 vale até 2026-08-31; padrão é 3/15)
    roteiro_entrada_por_milhao: float = 3.00
    roteiro_saida_por_milhao: float = 15.00

    # Z-Image Turbo na fal.ai — cobrado POR MEGAPIXEL, não por imagem.
    # É por isso que a resolução manda no custo: 1080x1920 são 2,07 MP.
    imagem_por_megapixel: float = 0.005

    # ElevenLabs — varia MUITO por plano. O modelo Flash cobra meio crédito
    # por caractere. Confira o seu plano antes de confiar neste número.
    narracao_por_mil_caracteres: float = 0.030

    # Groq whisper-large-v3-turbo, cobrado por hora de áudio.
    legenda_por_hora: float = 0.04

    dolar: float = 5.00


@dataclass
class Serie:
    """Os cinco parâmetros que definem uma série, conforme o mapa do projeto."""

    nicho: str
    idioma: str = "pt-BR"
    voz: str = ""                      # id da voz na ElevenLabs
    musica_fundo: Path | None = None
    estilo: str = "cinematográfico, iluminação dramática, alto contraste"
    legenda: bool = True

    # motor visual: no automático a direção escolhe onde movimento realmente
    # acrescenta valor e mantém imagens nas cenas de respiro.
    modo: str = "automatico"             # automatico | imagem | video
    modelo_video: str = "wan"

    # ritmo/duração
    cenas: int = 10                    # cortes curtos; ritmo vem da fala
    largura: int = 1080
    altura: int = 1920

    @property
    def megapixels(self) -> float:
        return (self.largura * self.altura) / 1_000_000


@dataclass
class Ambiente:
    anthropic: str | None = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    fal: str | None = field(default_factory=lambda: _env("FAL_KEY"))
    elevenlabs: str | None = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))
    groq: str | None = field(default_factory=lambda: _env("GROQ_API_KEY"))

    def faltando(self) -> list[str]:
        nomes = {
            "ANTHROPIC_API_KEY": self.anthropic,
            "FAL_KEY": self.fal,
            "ELEVENLABS_API_KEY": self.elevenlabs,
            "GROQ_API_KEY": self.groq,
        }
        return [n for n, v in nomes.items() if not v]


MODELO_ROTEIRO = "claude-sonnet-5"
MODELO_IMAGEM = "fal-ai/z-image/turbo"
MODELO_NARRACAO = "eleven_flash_v2_5"
MODELO_LEGENDA = "whisper-large-v3-turbo"
