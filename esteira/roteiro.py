"""Etapa 1 — roteiro, com Claude Sonnet 5.

Usa structured outputs: o schema garante o formato das cenas, então não
precisa de parser defensivo nem de retry por JSON malformado.
"""
from __future__ import annotations

from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .config import MODELO_ROTEIRO, Serie
from .custos import Custos

INSTRUCAO = """\
Você escreve roteiros de vídeo curto vertical para redes sociais.

Regras da narração:
- Os primeiros 3 segundos decidem tudo. Abra pelo fato mais surpreendente,
  nunca por saudação ou por anunciar o que virá.
- Frases curtas, voz ativa, linguagem falada. É para ser ouvido, não lido.
- Cada cena narra 1 ideia em uma frase de 7 a 16 palavras, pensada para durar
  de 2 a 4 segundos. Nunca esconda duas batidas narrativas na mesma cena.
- Sem "além disso", "por fim", "em resumo".
- Termine com uma frase que dê vontade de comentar, não com "se inscreva".
- A narração vai INTEIRA no idioma pedido, sem exceção: nomes de pessoa,
  de lugar, títulos de nobreza e obras entram na forma consagrada daquele
  idioma. "Henrique I da Inglaterra", nunca "Henrique the First". Não
  misture dois idiomas na mesma frase — quem ouve não lê legenda.

Regras de DIREÇÃO VISUAL:
- O prompt de imagem — e só ele — vai em inglês, porque os modelos de
  imagem respondem melhor. Isso não vale para a narração.
- Pense em batidas visuais de 2 a 4 segundos. As duas primeiras cenas formam
  juntas o gancho: a primeira interrompe o padrão; a segunda prova a promessa.
- Descreva uma AÇÃO concreta acontecendo agora: sujeito, verbo, ambiente,
  enquadramento, lente, luz e detalhes historicamente corretos. Evite retrato
  central parado, pessoa apenas olhando para a câmera e composição genérica.
- Varie deliberadamente plano geral, detalhe macro, ponto de vista, plongée,
  contra-plongée e silhueta. Cenas vizinhas não podem repetir o mesmo plano.
- Cenas vizinhas também não podem repetir a mesma ação ou composição. Quando
  o assunto continua, mostre uma consequência, detalhe ou ponto de vista novo.
- Nada de texto na imagem, nada de logotipo, nada de marca d'água.
- Enquadramento vertical 9:16. Deixe área negativa útil para a legenda na
  faixa inferior sem esconder a ação principal.
- Se um personagem aparece em mais de uma cena, a descrição física completa
  (rosto, cabelo, roupa, cores, acessórios) deve ser idêntica no prompt de
  imagem de cada cena em que ele aparece — palavra por palavra — para que o
  modelo de imagem, que gera cada cena isoladamente, o reconheça como a mesma
  pessoa.
- O campo movimento também vai em inglês e descreve câmera + movimento do
  sujeito, de modo filmável, curto e sem trocar a identidade do personagem.
- energia vai de 1 (respiro) a 5 (pico). papel é a função daquela batida na
  história. Cada vídeo precisa alternar intensidade, não ficar inteiro no 5.
- Defina uma paleta visual curta e mantenha-a em todos os prompts. O resultado
  deve parecer um filme dirigido, não imagens independentes de bancos diferentes.
"""


# O código de locale não serve como instrução: pedir "escreva em pt-BR" faz o
# modelo escorregar para nome próprio em inglês. O nome por extenso resolve.
# Espelha catalogo.IDIOMAS da plataforma, mas fica aqui porque a esteira é a
# camada de baixo e não importa de cima.
IDIOMAS: dict[str, str] = {
    "pt-BR": "português do Brasil",
    "en-US": "inglês americano",
    "es-ES": "espanhol da Espanha",
    "fr-FR": "francês",
    "de-DE": "alemão",
    "it-IT": "italiano",
    "nl-NL": "neerlandês",
}


class Cena(BaseModel):
    narracao: str = Field(description="O que a voz fala nesta cena, em uma ou duas frases.")
    imagem: str = Field(description="Prompt de imagem em inglês descrevendo a cena.")
    movimento: str = Field(
        description="Direção de câmera e movimento do sujeito, em inglês.")
    plano: Literal["geral", "medio", "close", "detalhe", "pov", "aereo"] = Field(
        description="Enquadramento dominante desta batida visual.")
    papel: Literal["gancho", "prova", "contexto", "virada", "escalada", "final"] = Field(
        description="Função narrativa desta cena.")
    energia: int = Field(ge=1, le=5, description="Intensidade visual de 1 a 5.")


class Roteiro(BaseModel):
    titulo: str = Field(description="Título curto para a publicação.")
    promessa: str = Field(description="A promessa do gancho em uma frase curta.")
    paleta: str = Field(description="Paleta consistente, em inglês, com 3 a 5 cores e luz.")
    som_ambiente: str = Field(
        description="Descrição curta, em inglês, de um som ambiente que combina com o vídeo.")
    cenas: list[Cena]


def gerar(serie: Serie, custos: Custos, assunto: str | None = None) -> Roteiro:
    cliente = anthropic.Anthropic()
    pedido = assunto or f"um vídeo novo sobre {serie.nicho}"

    resposta = cliente.messages.parse(
        model=MODELO_ROTEIRO,
        max_tokens=4000,
        system=INSTRUCAO,
        # Sonnet 5 não aceita mais temperature/top_p; a variação vem do prompt.
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{
            "role": "user",
            "content": (
                f"Escreva {pedido} em {IDIOMAS.get(serie.idioma, serie.idioma)}, "
                f"com exatamente "
                f"{serie.cenas} cenas. Estilo visual da série: {serie.estilo}. "
                f"Escolha um ângulo específico e pouco óbvio dentro do nicho — "
                f"não o tema mais previsível."
                f" A primeira cena precisa ser compreendida sem áudio e todas as cenas "
                f"devem incluir a mesma paleta no prompt de imagem."
            ),
        }],
        output_format=Roteiro,
    )

    uso = resposta.usage
    custos.roteiro(uso.input_tokens, uso.output_tokens)

    roteiro = resposta.parsed_output
    if roteiro is None:
        raise RuntimeError(f"roteiro não veio no formato esperado ({resposta.stop_reason})")
    return roteiro
