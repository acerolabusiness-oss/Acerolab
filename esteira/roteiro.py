"""Etapa 1 — roteiro, com Claude Sonnet 5.

Usa structured outputs: o schema garante o formato das cenas, então não
precisa de parser defensivo nem de retry por JSON malformado.
"""
from __future__ import annotations

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
- Cada cena narra 1 ideia. Sem "além disso", "por fim", "em resumo".
- Termine com uma frase que dê vontade de comentar, não com "se inscreva".
- A narração vai INTEIRA no idioma pedido, sem exceção: nomes de pessoa,
  de lugar, títulos de nobreza e obras entram na forma consagrada daquele
  idioma. "Henrique I da Inglaterra", nunca "Henrique the First". Não
  misture dois idiomas na mesma frase — quem ouve não lê legenda.

Regras do prompt de imagem:
- O prompt de imagem — e só ele — vai em inglês, porque os modelos de
  imagem respondem melhor. Isso não vale para a narração.
- Descreva a CENA concreta: sujeito, ação, ambiente, enquadramento, luz.
- Nada de texto na imagem, nada de logotipo, nada de marca d'água.
- Enquadramento vertical, o sujeito ocupando o terço central.
- Se um personagem aparece em mais de uma cena, a descrição física completa
  (rosto, cabelo, roupa, cores, acessórios) deve ser idêntica no prompt de
  imagem de cada cena em que ele aparece — palavra por palavra — para que o
  modelo de imagem, que gera cada cena isoladamente, o reconheça como a mesma
  pessoa.
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


class Roteiro(BaseModel):
    titulo: str = Field(description="Título curto para a publicação.")
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
