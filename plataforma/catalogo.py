"""O que o cliente pode escolher no wizard.

Este arquivo é o "melhor dos dois" da ficha técnica, virado em dado:

  · nichos e idiomas na largura da ClipShort (14 e 7, contra 8 e 3)
  · voz com descrição de tom E prévia em áudio — um de cada concorrente
  · música com gênero e sorteio por vídeo
  · estilo visual com miniatura, que a ClipShort não tem
  · estilo de legenda, que a ClipShort não tem etapa

Tudo aqui é conteúdo, não código: crescer a lista não custa nada e é a
diferença mais barata que existe entre a nossa primeira tela e a deles.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from esteira.config import RAIZ

MUSICAS = RAIZ / "recursos" / "musicas"
MINIATURAS = RAIZ / "plataforma" / "estatico" / "estilos"


# ─────────────────────────────── nicho ───────────────────────────────

@dataclass(frozen=True)
class Nicho:
    chave: str
    nome: str
    resumo: str          # o que o cliente lê
    prompt: str          # o que o roteirista recebe
    alta: bool = False   # "em alta agora"

    @property
    def capa(self) -> str:
        # Cada nicho tem uma direção de arte própria. Não reutilize imagens do
        # mural aqui: a repetição faz temas diferentes parecerem o mesmo produto.
        return f"/estatico/nichos/{self.chave}.webp"


NICHOS: tuple[Nicho, ...] = (
    Nicho("terror", "Terror",
          "Histórias de terror originais, inventadas do zero a cada vídeo.",
          "histórias de terror originais e autocontidas, com uma virada no fim",
          alta=True),
    Nicho("biblicas", "Histórias bíblicas",
          "As narrativas do texto com peso dramático, sem sermão.",
          "episódios bíblicos narrados com peso dramático, sem tom de pregação"),
    Nicho("true-crime", "Crimes reais",
          "Casos documentados, contados com frieza e respeito às vítimas.",
          "casos criminais reais e documentados, contados com precisão e sem sensacionalismo"),
    Nicho("medieval", "Medieval",
          "Reis, cercos e traições, com peso de crônica.",
          "episódios da história medieval europeia: política, cercos, traições",
          alta=True),
    Nicho("mitologia", "Mitologia",
          "Deuses, monstros e escolhas com preço alto, além do óbvio.",
          "mitos de várias culturas, priorizando os menos batidos que o panteão grego"),
    Nicho("e-se", "E se...",
          "Cenários hipotéticos levados a sério, com consequências reais.",
          "cenários contrafactuais desenvolvidos com rigor: o que mudaria, em cadeia",
          alta=True),
    Nicho("espaco", "Espaço e universo",
          "Escala cósmica traduzida em comparações que desestabilizam.",
          "astronomia e cosmologia, traduzindo escalas em comparações concretas"),
    Nicho("estoicismo", "Estoicismo",
          "Filosofia prática aplicada a um problema moderno por vez.",
          "filosofia estoica aplicada a um problema concreto da vida moderna"),
    Nicho("lendas", "Lendas urbanas",
          "O que a cidade conta baixinho — e de onde a história saiu.",
          "lendas urbanas, incluindo a origem rastreável de cada uma",
          alta=True),
    Nicho("historia", "Eventos históricos",
          "O dia em que algo mudou, e por que quase ninguém percebeu na hora.",
          "eventos históricos decisivos, com foco em por que passaram despercebidos"),
    Nicho("curiosidades", "Curiosidades",
          "Fatos verificáveis que reorganizam o que você achava que sabia.",
          "curiosidades verificáveis e surpreendentes, sem factoide falso"),
    Nicho("financas", "Educação financeira",
          "Uma decisão de dinheiro por vídeo, com a conta na tela.",
          "educação financeira prática: uma decisão por vídeo, com números"),
    Nicho("biografias", "Biografias",
          "A parte da trajetória que ninguém conta nas palestras.",
          "biografias curtas com foco no período difícil, não no resultado"),
    Nicho("conspiracao", "Teorias da conspiração",
          "A teoria, quem a inventou e o que os fatos dizem.",
          "teorias conspiratórias apresentadas com sua origem e o que a evidência mostra"),
)

NICHO_POR_CHAVE = {n.chave: n for n in NICHOS}


# ────────────────────────────── idioma ───────────────────────────────

@dataclass(frozen=True)
class Idioma:
    codigo: str
    nome: str
    bandeira: str


IDIOMAS: tuple[Idioma, ...] = (
    Idioma("pt-BR", "Português (Brasil)", "🇧🇷"),
    Idioma("en-US", "English (US)", "🇺🇸"),
    Idioma("es-ES", "Español", "🇪🇸"),
    Idioma("fr-FR", "Français", "🇫🇷"),
    Idioma("de-DE", "Deutsch", "🇩🇪"),
    Idioma("it-IT", "Italiano", "🇮🇹"),
    Idioma("nl-NL", "Nederlands", "🇳🇱"),
)

IDIOMA_POR_CODIGO = {i.codigo: i for i in IDIOMAS}


# ─────────────────────────────── voz ─────────────────────────────────

@dataclass(frozen=True)
class Voz:
    id: str              # id na ElevenLabs
    nome: str
    genero: str
    tom: str             # a descrição que o AutoShortz tem e a ClipShort não


# Vozes públicas da biblioteca da ElevenLabs. O modelo multilíngue narra em
# qualquer idioma com qualquer uma delas — o timbre é que muda, não a língua.
#
# ATENÇÃO: confira os ids na sua conta antes de vender. Voz clonada própria
# soa melhor e não some da biblioteca pública de um dia para o outro; o
# endpoint /v1/voices lista as suas e substitui esta tabela.
VOZES: tuple[Voz, ...] = (
    Voz("pNInz6obpgDQGcFmaJgB", "Rafael", "Masculina",
        "Grave e contido. O padrão para suspense e história."),
    Voz("TxGEqnHWrfWFTfGW9XjX", "Heitor", "Masculina",
        "Próximo e sussurrado. Arrepia em terror e lenda urbana."),
    Voz("ErXwobaYiN019PkySvjV", "Vicente", "Masculina",
        "Preciso, tom de documentário. Feito para crime real."),
    Voz("EXAVITQu4vr4xnSDxMaL", "Bianca", "Feminina",
        "Tensa e baixa. Segura o clima em terror e mistério."),
    Voz("21m00Tcm4TlvDq8ikWAM", "Clara", "Feminina",
        "Viva e expressiva. Boa para curiosidade e espaço."),
    Voz("AZnzlk1XvdvUeBnXmlld", "Núbia", "Feminina",
        "Quente e firme. Vai bem em biografia e estoicismo."),
)

VOZ_POR_ID = {v.id: v for v in VOZES}

# Frase da prévia: curta o bastante para custar quase nada e longa o
# bastante para dar pra ouvir o timbre.
AMOSTRA = {
    "pt-BR": "Ninguém percebeu naquela noite, mas tudo já tinha mudado.",
    "en-US": "Nobody noticed that night, but everything had already changed.",
    "es-ES": "Nadie se dio cuenta esa noche, pero todo ya había cambiado.",
    "fr-FR": "Personne ne l'a remarqué cette nuit-là, mais tout avait déjà changé.",
    "de-DE": "In jener Nacht bemerkte es niemand, doch alles hatte sich schon geändert.",
    "it-IT": "Nessuno se ne accorse quella notte, ma tutto era già cambiato.",
    "nl-NL": "Niemand merkte het die nacht, maar alles was al veranderd.",
}


# ────────────────────────────── música ───────────────────────────────

@dataclass(frozen=True)
class Musica:
    arquivo: str
    nome: str
    genero: str
    autor: str = ""
    licenca: str = ""
    vibe: str = ""
    destaque: bool = False

    @property
    def caminho(self) -> Path:
        return MUSICAS / self.arquivo

    @property
    def existe(self) -> bool:
        return self.caminho.exists()


# O nome do arquivo é a chave. Ponha os mp3 em recursos/musicas/ com estes
# nomes — o que faltar simplesmente não aparece no wizard, em vez de virar
# uma opção que quebra na hora de gerar.
MUSICAS_CATALOGO: tuple[Musica, ...] = (
    Musica("melodia-sinistra.mp3", "Melodia sinistra", "Terror",
           "John Bartmann", "CC0"),
    Musica("piano-de-terror.mp3", "Piano de terror", "Terror"),
    Musica("misterio-sem-solucao.mp3", "Mistério sem solução", "Suspense",
           "John Bartmann", "CC0"),
    Musica("calmaria.mp3", "Calmaria antes da tempestade", "Suspense",
           "John Bartmann", "CC0"),
    Musica("sinfonia-epica.mp3", "Sinfonia épica", "Épico"),
    Musica("marcha-lenta.mp3", "Marcha lenta", "Épico"),
    Musica("oito-bits.mp3", "8-bit sombrio", "Retrô"),
    Musica("respiro.mp3", "Respiro", "Reflexivo",
           "John Bartmann", "CC0"),
    Musica("horizonte.mp3", "Horizonte", "Motivacional",
           "John Bartmann", "CC0"),
    Musica("pulso-noturno.mp3", "Pulso noturno", "Hip hop urbano",
           "Loyalty Freak Music", "CC0", "cortes rápidos", True),
    Musica("lofi-depois-da-meia-noite.mp3", "Depois da meia-noite", "Lo-fi hip hop",
           "Loyalty Freak Music", "CC0", "storytelling", True),
    Musica("rua-em-movimento.mp3", "Rua em movimento", "Hip hop instrumental",
           "Loyalty Freak Music", "CC0", "listas e curiosidades", True),
    Musica("neon-acelerado.mp3", "Neon acelerado", "Synthwave / techno",
           "Loyalty Freak Music", "CC0", "tecnologia e impacto", True),
    Musica("onda-de-verao.mp3", "Onda de verão", "Chill beat",
           "Loyalty Freak Music", "CC0", "lifestyle", True),
)


def musicas_disponiveis() -> list[Musica]:
    """Só o que existe em disco. Opção que não toca não vai pra tela."""
    return [m for m in MUSICAS_CATALOGO if m.existe]


def sortear_musica(escolhidas: list[str]) -> Path | None:
    """Uma música por vídeo, sorteada entre as que o cliente marcou.

    É o detalhe do AutoShortz que a ClipShort não tem, e é o que impede a
    série inteira de soar igual.
    """
    validas = [m for m in MUSICAS_CATALOGO if m.arquivo in escolhidas and m.existe]
    return random.choice(validas).caminho if validas else None


MODOS_MUSICA = frozenset({"biblioteca", "viral", "sem_musica"})


@dataclass(frozen=True)
class SomPlataforma:
    chave: str
    nome: str
    biblioteca: str
    url: str
    url_ouvir: str
    rotulo_ouvir: str
    instrucao: str
    alcance: str


# Música popular muda por país, conta e dia. O ACEROLAB não promete uma faixa
# específica: prepara o vídeo sem trilha e leva a pessoa ao catálogo comercial
# oficial, onde a licença é aplicada pela própria plataforma no envio.
SONS_PLATAFORMA: tuple[SomPlataforma, ...] = (
    SomPlataforma(
        "tiktok", "TikTok", "Commercial Music Library",
        "https://ads.tiktok.com/help/article/how-to-use-the-commercial-music-library?lang=pt",
        "https://ads.tiktok.com/business/creativecenter/pc/en",
        "Ouvir sons em alta",
        "No TikTok, toque em Adicionar som e escolha uma faixa comercial em alta no Brasil.",
        "orgânico e anúncios, conforme a faixa",
    ),
    SomPlataforma(
        "instagram", "Instagram", "Meta Sound Collection",
        "https://www.facebook.com/help/instagram/402084904469945",
        "https://www.facebook.com/sound/collection",
        "Ouvir Sound Collection",
        "No Reels, toque em Áudio e escolha uma faixa liberada para uso comercial.",
        "Reels, Stories e anúncios",
    ),
    SomPlataforma(
        "youtube", "YouTube Shorts", "Biblioteca de áudio do Shorts",
        "https://support.google.com/youtube/answer/13053317?hl=pt-BR",
        "https://www.youtube.com/audiolibrary",
        "Ouvir biblioteca segura",
        "No Shorts, toque em Adicionar som antes de publicar; não reenvie o áudio fora do YouTube.",
        "Shorts, conforme a licença exibida",
    ),
)
SOM_PLATAFORMA_POR_CHAVE = {p.chave: p for p in SONS_PLATAFORMA}


def configurar_musica(modo: str, plataforma: str,
                      escolhidas: list[str]) -> tuple[str, str, list[str]]:
    """Valida a estratégia de áudio recebida do formulário.

    O modo viral pode conservar a seleção para uma futura troca de modo, mas
    a fila ignora essas trilhas: o arquivo sai apenas com narração para a
    licença da plataforma ser aplicada no momento do upload.
    """
    modo = modo if modo in MODOS_MUSICA else "biblioteca"
    plataforma = plataforma if plataforma in SOM_PLATAFORMA_POR_CHAVE else "tiktok"
    permitidas = {m.arquivo for m in musicas_disponiveis()}
    musicas = list(dict.fromkeys(m for m in escolhidas if m in permitidas))
    if modo == "biblioteca":
        return modo, "", musicas
    if modo == "viral":
        return modo, plataforma, musicas
    return "sem_musica", "", musicas


# ─────────────────────────── estilo visual ───────────────────────────

@dataclass(frozen=True)
class Estilo:
    chave: str
    nome: str
    prompt: str          # entra no prompt de cada imagem

    @property
    def miniatura(self) -> str:
        """Amostra real quando existe; referência do acervo como fallback."""
        arq = MINIATURAS / f"{self.chave}.webp"
        if arq.exists():
            return f"/estatico/estilos/{self.chave}.webp"
        return f"/estatico/mural/{CAPAS_ESTILO.get(self.chave, 'q8.webp')}"

    @property
    def miniatura_real(self) -> bool:
        return (MINIATURAS / f"{self.chave}.webp").exists()


CAPAS_ESTILO: dict[str, str] = {
    "cinematografico": "q2.webp",
    "terror": "q13.webp",
    "medieval": "q6.webp",
    "quadrinhos": "q4.webp",
    "xilogravura": "q11.webp",
    "anime": "q7.webp",
    "render3d": "q1.webp",
    "fotorrealismo": "q9.webp",
    "astrofoto": "q8.webp",
}


ESTILOS: tuple[Estilo, ...] = (
    Estilo("cinematografico", "Cinematográfico",
           "cinematic still, dramatic lighting, high contrast, shallow depth of field, 35mm film grain"),
    Estilo("terror", "Terror ilustrado",
           "dark horror illustration, heavy ink shadows, muted desaturated palette, unsettling composition"),
    Estilo("medieval", "Medieval",
           "medieval manuscript painting style, warm torchlight, stone and cloth texture, period accurate"),
    Estilo("quadrinhos", "Quadrinhos",
           "graphic novel panel, bold ink outlines, flat cel shading, dramatic angle"),
    Estilo("xilogravura", "Xilogravura",
           "woodcut print, black and white carved lines, high contrast, folk art texture"),
    Estilo("anime", "Anime",
           "anime key visual, clean linework, vibrant cel shading, expressive lighting"),
    Estilo("render3d", "Animação 3D",
           "stylized 3d render, soft global illumination, subsurface scattering, pixar-like character design"),
    Estilo("fotorrealismo", "Fotorrealismo",
           "photorealistic, natural lighting, sharp focus, 50mm lens, documentary photography"),
    Estilo("astrofoto", "Astrofotografia",
           "deep space astrophotography, nebula colors, star field, long exposure, hubble-like detail"),
)

ESTILO_POR_CHAVE = {e.chave: e for e in ESTILOS}


# ────────────────────────── estilo de legenda ────────────────────────

@dataclass(frozen=True)
class Legenda:
    chave: str
    nome: str
    cor: str             # preenchimento
    contorno: str        # cor do traço
    caixa_alta: bool
    peso_contorno: int   # divisor do corpo: quanto menor, mais grosso


LEGENDAS: tuple[Legenda, ...] = (
    Legenda("traco-forte", "Traço forte", "#FFFFFF", "#000000", True, 10),
    Legenda("destaque", "Destaque vermelho", "#FF3B30", "#000000", True, 10),
    Legenda("suave", "Suave", "#FFFFFF", "#000000", True, 18),
    Legenda("impacto", "Impacto", "#FFFFFF", "#000000", False, 7),
)

LEGENDA_POR_CHAVE = {l.chave: l for l in LEGENDAS}


# ───────────────────────────── duração ───────────────────────────────

@dataclass(frozen=True)
class Duracao:
    chave: str
    nome: str
    cenas: int
    aviso: str = ""


DURACOES: tuple[Duracao, ...] = (
    Duracao("curto", "30 a 60 segundos", 10),
    Duracao("longo", "60 a 90 segundos", 16,
            "Custa cerca de 1,6x o vídeo curto — mais imagens e mais narração."),
)

DURACAO_POR_CHAVE = {d.chave: d for d in DURACOES}


# ─────────────────────────── redes sociais ───────────────────────────

@dataclass(frozen=True)
class Rede:
    chave: str
    nome: str
    disponivel: bool
    motivo: str


# Ficam visíveis e desligadas de propósito. A ClipShort deixa vincular
# depois; nós deixamos ver o que vem depois. Ligar isto depende de auditoria
# do Google e do TikTok, não de código nosso.
REDES: tuple[Rede, ...] = (
    Rede("youtube", "YouTube", False, "Aguardando verificação do aplicativo no Google."),
    Rede("tiktok", "TikTok", False, "Aguardando auditoria da API de publicação."),
)


# ─────────────────────────── modo das cenas ──────────────────────────

# A escolha mais cara do produto, e por isso a única que mostra preço na
# tela. Imagem é foto gerada com zoom lento por cima; vídeo é clipe gerado,
# cobrado POR SEGUNDO. O número medido numa execução real de 7 cenas foi
# R$ 0,69 no modo imagem — as estimativas de vídeo saem de `esteira.clipes`
# para não existirem dois preços diferentes no mesmo repositório.

CUSTO_BASE_DOLAR = 0.0335   # roteiro + narração + legenda, medido em 16/08/2026
CUSTO_IMAGEM_DOLAR = 0.1037  # 10 cenas de 2,07 MP a US$ 0,005/MP
DOLAR = 5.00
