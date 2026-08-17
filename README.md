# ACEROLAB

Duas partes:

| | O que é | Como roda |
|---|---|---|
| `site/` | A landing: fonte + montador que embute fonte, imagem e vídeo | `python site/montar.py landing.html` |
| `plataforma/` | O produto: entrar, montar série, propor tema, gerar, baixar | `python -m plataforma` |
| `esteira/` | A produção: roteiro → imagens → narração → legendas → MP4 | `python -m esteira` |

Com a plataforma no ar, `/` é a landing, `Entrar` leva ao login e quem já entrou
cai direto no painel.

O objetivo deste código **não é só produzir vídeo**. É responder à pergunta
que decide a franquia: *quanto custa de verdade um vídeo?* A tabela do
franqueador diz R$ 0,18 a R$ 0,36. Com os 20% de royalty por cima, uma
diferença de centavos aqui decide se a operação dá lucro ou prejuízo.

## Instalar

```sh
cd ~/acerolab
python3 -m venv .venv && source .venv/bin/activate
pip install -r requisitos.txt
cp .env.exemplo .env      # e preencha as quatro chaves
```

Precisa de `ffmpeg` no PATH (`brew install ffmpeg`).

## Rodar

```sh
# um vídeo, para conferir se a saída presta
python -m esteira --nicho "curiosidades da história" --cenas 7

# a medição que interessa
python -m esteira --nicho "curiosidades da história" --repetir 50
```

Cada vídeo cai em `saida/<data-hora>/video_NNN/` com o MP4, o roteiro em
JSON e o `custo.json` da unidade. No fim sai o consolidado.

### Opções

| Flag | Para quê |
|---|---|
| `--cenas 5\|7\|9` | Equivale às três colunas da tabela de custo |
| `--repetir N` | Tamanho da amostra |
| `--largura/--altura` | **Manda no custo de imagem** — veja abaixo |
| `--voz` | ID da voz na ElevenLabs |
| `--musica arquivo.mp3` | Trilha de fundo (entra a 10% de volume) |
| `--sem-legenda` | Pula a transcrição |
| `--modo imagem\|video` | Cena estática com movimento (padrão, é o da tabela) ou clipe gerado |
| `--modelo-video wan\|seedance\|kling` | Só com `--modo video` |
| `--segundos-cena 5` | Duração de cada clipe — é o que a fal.ai cobra |
| `--dolar 5.40` | Câmbio usado na conversão do relatório |

## O que já sabemos antes de rodar

**A fal.ai cobra por megapixel, não por imagem** — US$ 0,005/MP.

| Resolução | MP | Custo/imagem | 7 imagens |
|---|---|---|---|
| 1080×1920 (vertical cheio) | 2,07 | US$ 0,0104 | US$ 0,073 |
| 720×1280 | 0,92 | US$ 0,0046 | US$ 0,032 |
| Implícito na tabela do franqueador | ~0,6 | US$ 0,0030 | US$ 0,021 |

A tabela assume imagem de ~600×1000, **abaixo da resolução de vídeo
vertical**. Em 1080×1920 essa linha sozinha já estoura o total previsto.
Rode nas duas resoluções e compare a qualidade: se 720×1280 aguentar, a
conta muda de figura.

**Imagem que se move ≠ vídeo gerado — e a diferença é de 30x.** A tabela do
franqueador lista "Imagens — Z-Image Turbo", que é modelo de **imagem**. O
movimento vem do render (Ken Burns), não de um modelo de vídeo. É por isso
que a conta dele fecha em centavos:

| Modo | Como cobra | 7 cenas / 35s |
|---|---|---|
| `--modo imagem` (Z-Image Turbo) | por megapixel | US$ 0,03 a 0,07 |
| `--modo video` (Wan 2.5, o mais barato) | por segundo, US$ 0,05/s | **US$ 1,75** |
| `--modo video` (Kling v2) | US$ 0,224/s | US$ 7,84 |

Com receita de ~R$ 0,99 por vídeo, o modo vídeo dá **prejuízo de ~R$ 7,75 por
vídeo**. Ele existe aqui só para a comparação sair medida, não no achismo — e
para responder à pergunta que precisa ir ao franqueador: *o produto dele é
imagem com movimento ou vídeo gerado?* Se for vídeo, a tabela está errada por
34x. O padrão é `imagem` porque é o que a tabela descreve.

**A linha da ElevenLabs também é otimista.** US$ 0,015 para ~30s de fala só
fecha com o modelo Flash em plano de tier alto. Confira o seu plano — no
Creator, a mesma narração custa várias vezes isso.

**O render não está na tabela.** Não é custo de API, é CPU: num servidor,
vira hora de máquina. O relatório mede o tempo para o número existir.

**Falha custa.** Um vídeo que quebra no render já pagou roteiro, imagens e
narração. O consolidado mostra as falhas separadamente por isso.

## Como ler o resultado

O relatório final mostra o custo médio por vídeo e a fatia de cada etapa.

- **Até ~R$ 0,35** — a franquia fecha, pode ir com tudo.
- **Acima de ~R$ 0,50** — renegocie os 20% *antes* de assinar, com esta
  planilha na mão.

Falta somar ainda: storage e banda dos MP4, refação (vídeo que o cliente
manda refazer), gateway de pagamento (~5%) e imposto (~6-15%).

## Estrutura

| Arquivo | Etapa |
|---|---|
| `config.py` | Preços e os cinco parâmetros da série |
| `custos.py` | Contabilidade e relatório |
| `roteiro.py` | Claude Sonnet 5, saída estruturada |
| `imagens.py` | Z-Image Turbo na fal.ai, em paralelo (`--modo imagem`) |
| `clipes.py` | Modelos de vídeo na fal.ai, cobrados por segundo (`--modo video`) |
| `narracao.py` | ElevenLabs |
| `legendas.py` | Groq Whisper → ASS palavra a palavra |
| `legenda_png.py` | Legenda sem libass: um PNG por palavra, via `overlay` |
| `render.py` | ffmpeg: Ken Burns (imagem) ou enquadramento 9:16 (clipe) + áudio + legenda |
| `__main__.py` | Orquestrador e medição |

Da plataforma:

| Arquivo | Papel |
|---|---|
| `banco.py` | SQLite: esquema e acesso |
| `contas.py` | Cadastro, senha (scrypt) e sessão |
| `catalogo.py` | Tudo que o cliente pode escolher no wizard |
| `temas.py` | A série propondo pauta, sem repetir o que já propôs |
| `fila.py` | O trabalhador que roda a esteira, um vídeo por vez |
| `miniaturas.py` | Gera a amostra de cada estilo visual, uma vez só |
| `app.py` | Rotas |

## A plataforma (fase 1)

```sh
.venv/bin/python -m plataforma          # http://127.0.0.1:8000
.venv/bin/python -m plataforma.miniaturas   # amostra de cada estilo visual, uma vez só
```

Banco em `acerolab.db` (SQLite, um arquivo — dá pra copiar como backup).
A fila roda dentro do mesmo processo, um vídeo por vez.

**O wizard tem 7 passos**, somando o melhor dos dois concorrentes:

| Passo | Vem de | O detalhe |
|---|---|---|
| Nicho | ClipShort | 14 prontos + personalizado (o AutoShortz tem 8) |
| Idioma e voz | os dois | 7 idiomas, e a voz tem descrição de tom **e** botão de ouvir |
| Música | os dois | com prévia e gênero; marca várias e **sorteia uma por vídeo** |
| Estilo visual | AutoShortz | 9 estilos **com amostra real** — a ClipShort mostra só o nome |
| Estilo de legenda | AutoShortz | 4 estilos; a ClipShort não tem essa etapa |
| Publicar sozinho | — | visível e **desligado**, com o motivo escrito |
| Detalhes | ClipShort | nome e duração (30–60s ou 60–90s) |

**O que nenhum dos dois faz, e já está aqui:**

- **A série propõe a pauta antes de gastar.** Título e gancho primeiro; imagem e
  narração só depois do seu OK. Pauta é texto e custa centavos — é o que corta a
  refação, o custo invisível que nenhuma das duas tabelas contabiliza.
- **Memória da série.** Os temas já propostos entram no pedido como lista do que
  não repetir.
- **Erro que dá pra entender.** `fila.humanizar()` traduz a mensagem do fornecedor
  antes de ela chegar na tela.
- **Vídeo que falha não some.** Fica com o motivo, porque as etapas anteriores já
  foram cobradas de nós.

## O que ainda não está pronto

Checkout e Pix, agendamento por horário, publicação automática e painel de
desempenho. As duas últimas dependem de verificação do aplicativo no Google e
de auditoria do TikTok — processo de meses, que corre em paralelo ao código.
A ficha técnica com a ordem inteira está em `spec/ficha.html`.
