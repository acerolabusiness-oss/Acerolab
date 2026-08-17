"""Termos de uso e política de privacidade.

**Isto é uma minuta, não uma peça jurídica pronta.** Está escrito com base no
que a plataforma faz de fato — quais dados entram, para onde vão, o que a
pessoa recebe — e é honesto sobre isso. Mas contrato de consumo no Brasil
puxa CDC e LGPD, e antes de cobrar do primeiro cliente isso precisa passar
por um advogado. O aviso disso vai impresso no topo das duas páginas
enquanto `REVISADO` for False.

Manter o texto aqui, e não num HTML solto, tem uma razão prática: a lista de
subcontratados é a mesma que a esteira usa. Quando trocar de fornecedor de
voz, muda em um lugar e o documento acompanha.
"""
from __future__ import annotations

from dataclasses import dataclass

# Vire para True só depois que um advogado tiver revisado os dois textos.
REVISADO = False

ATUALIZADO = "15 de agosto de 2026"
EMPRESA = "ACEROLAB"
CONTATO = "contato@acerolab.com.br"


@dataclass(frozen=True)
class Parte:
    titulo: str
    paragrafos: tuple[str, ...]


@dataclass(frozen=True)
class Documento:
    chave: str
    titulo: str
    resumo: str
    partes: tuple[Parte, ...]


# Quem processa dado do cliente na nossa operação. É a mesma lista da
# esteira — se ela mudar lá, muda aqui.
SUBCONTRATADOS: tuple[tuple[str, str], ...] = (
    ("Anthropic", "escreve o roteiro e as pautas a partir do nicho que você escolheu"),
    ("fal.ai", "gera as imagens das cenas"),
    ("ElevenLabs", "converte o roteiro em narração"),
    ("Groq", "transcreve a narração para sincronizar a legenda"),
    ("Supabase", "guarda seu e-mail e sua senha quando você entra pela plataforma"),
    ("Google", "confirma sua identidade quando você entra com a conta Google"),
)

_lista_sub = "; ".join(f"{nome} ({papel})" for nome, papel in SUBCONTRATADOS)


TERMOS = Documento(
    "termos", "Termos de uso",
    "O que a ACEROLAB entrega, o que é seu, e o que não pode.",
    (
        Parte("O que é a ACEROLAB", (
            "A ACEROLAB é uma ferramenta de produção de vídeo curto. Você define uma "
            "série — o assunto, o idioma, a voz, o estilo visual e o formato da legenda "
            "— e a plataforma propõe temas dentro dela. Quando você manda gerar um tema, "
            "a plataforma escreve o roteiro, cria as imagens, narra, legenda e entrega "
            "um arquivo de vídeo vertical pronto para publicar.",
            "Nada é gerado sem que você mande gerar. Tema proposto que você não aprova "
            "não vira vídeo e não consome nada do seu plano.",
        )),
        Parte("O vídeo é seu", (
            "O que a plataforma produz a partir da sua série é seu. Você pode publicar, "
            "editar, monetizar e usar comercialmente, sem precisar dar crédito à ACEROLAB.",
            "Nós guardamos uma cópia dos seus vídeos enquanto sua conta existir, para "
            "você poder baixar de novo. Se você encerrar a conta, apagamos.",
        )),
        Parte("O que a ACEROLAB não garante", (
            "O conteúdo é gerado por inteligência artificial e pode conter erro de fato, "
            "data trocada ou afirmação imprecisa. A conferência antes de publicar é sua — "
            "é por isso que a plataforma mostra o tema e o título antes de produzir.",
            "Modelos de IA podem gerar resultados parecidos para pedidos parecidos. Não "
            "garantimos que o seu vídeo será único em relação ao de outro cliente, nem "
            "que qualquer vídeo terá determinado alcance, número de visualizações ou receita.",
            "Não garantimos que a plataforma ficará disponível sem interrupção. "
            "Dependemos de serviços de terceiros que podem falhar ou mudar de preço "
            "e de regra sem aviso a nós.",
        )),
        Parte("O que você não pode gerar", (
            "É proibido usar a plataforma para produzir: conteúdo sexual envolvendo "
            "menores; incitação a violência, ódio ou discriminação; desinformação sobre "
            "saúde, eleição ou processo democrático; imitação de pessoa real sem "
            "autorização; material que viole direito autoral de terceiro; e qualquer "
            "coisa proibida por lei brasileira.",
            "Também é proibido revender acesso à plataforma ou automatizar o uso da "
            "conta por fora da interface, sem acordo por escrito.",
            "Conta que descumprir isso pode ser suspensa sem aviso, e sem devolução do "
            "valor do período em andamento.",
        )),
        Parte("Publicação nas suas redes", (
            "Quando a publicação automática estiver disponível, conectar seu canal do "
            "YouTube ou do TikTok é opcional e reversível. Nós recebemos apenas a "
            "autorização de publicar; não lemos suas mensagens, não alteramos o que já "
            "está no canal e não desconectamos nada sem você pedir.",
            "Você continua sujeito às regras da plataforma onde publica. Uma remoção ou "
            "punição aplicada pelo YouTube ou pelo TikTok ao seu canal é uma relação "
            "entre você e eles.",
        )),
        Parte("Pagamento e cancelamento", (
            "A assinatura é cobrada por série, no ciclo escolhido, e renova sozinha até "
            "você cancelar. Cancelar interrompe as próximas cobranças e mantém o acesso "
            "até o fim do período já pago.",
            "Você pode desistir e pedir devolução integral em até 7 dias do primeiro "
            "pagamento, conforme o artigo 49 do Código de Defesa do Consumidor.",
            "Se um vídeo falhar por erro nosso, ele não conta no seu plano e é refeito "
            "sem custo.",
        )),
        Parte("Mudanças nestes termos", (
            f"Se mudarmos algo relevante, avisamos por e-mail com pelo menos 30 dias de "
            f"antecedência. Se você não concordar, pode cancelar antes de a mudança "
            f"valer. Dúvidas: {CONTATO}.",
        )),
    ),
)


PRIVACIDADE = Documento(
    "privacidade", "Política de privacidade",
    "Que dado a gente coleta, para que serve, e com quem compartilha.",
    (
        Parte("O que a gente coleta", (
            "Da sua conta: nome, e-mail e — quando você não entra pelo Google — uma "
            "versão embaralhada da sua senha, que não permite descobrir a senha original.",
            "Do seu uso: as séries que você monta, os temas propostos, os vídeos gerados "
            "e o custo de produção de cada um. Registros técnicos de acesso, como data, "
            "hora e endereço IP, guardados por 6 meses conforme o Marco Civil da Internet.",
            "Não coletamos dados de pagamento. Quando houver cobrança, ela passa por um "
            "provedor de pagamento que recebe esses dados direto de você.",
        )),
        Parte("Para que serve", (
            "Para produzir o que você pediu, manter sua conta, cobrar a assinatura, "
            "responder seu suporte e melhorar a plataforma. Nada além disso.",
            "Não vendemos seus dados. Não usamos o conteúdo das suas séries para treinar "
            "modelo de inteligência artificial nosso nem de terceiro.",
        )),
        Parte("Com quem a gente compartilha", (
            "Para produzir o vídeo, o texto da sua série passa por serviços "
            f"especializados: {_lista_sub}.",
            "Cada um recebe apenas o necessário para a sua parte — o serviço de voz, por "
            "exemplo, recebe o roteiro e não recebe seu e-mail. Nenhum deles recebe "
            "sua senha.",
            "Alguns desses serviços ficam fora do Brasil, o que significa transferência "
            "internacional de dados. Ao usar a plataforma, você concorda com isso.",
        )),
        Parte("Seus direitos (LGPD)", (
            "Você pode, a qualquer momento, pedir: confirmação de que tratamos seus "
            "dados; acesso a eles; correção do que estiver errado; portabilidade; e "
            "eliminação dos dados que não somos obrigados a guardar por lei.",
            f"É só escrever para {CONTATO}. Respondemos em até 15 dias.",
        )),
        Parte("Por quanto tempo a gente guarda", (
            "Enquanto sua conta existir. Encerrada a conta, apagamos séries e vídeos em "
            "até 30 dias. Registros de acesso e dados fiscais ficam pelo prazo que a lei "
            "exige, e só para isso.",
        )),
        Parte("Segurança", (
            "Senha é guardada embaralhada, nunca em texto puro. O acesso ao banco é "
            "restrito. Ainda assim, nenhum sistema é inviolável: se acontecer um "
            "incidente que possa te afetar, avisamos você e a Autoridade Nacional de "
            "Proteção de Dados, como a lei manda.",
        )),
        Parte("Cookies", (
            "Usamos um cookie próprio só para manter você conectado. Ele não segue você "
            "por outros sites e não serve para publicidade.",
        )),
    ),
)


DOCUMENTOS = {d.chave: d for d in (TERMOS, PRIVACIDADE)}
