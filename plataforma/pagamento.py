"""Cobrança com Stripe.

O desenho é o mesmo do login: o Stripe guarda o meio de pagamento e toca a
recorrência; o nosso banco guarda o que a assinatura *libera* (quantas
séries, qual ritmo). Assim nenhuma outra parte do sistema precisa saber que
o Stripe existe.

**Uma limitação do Brasil que muda o produto:** assinatura recorrente no
Stripe brasileiro é **cartão**. Pix no Stripe funciona para cobrança avulsa,
não para renovar sozinho todo mês. Ou seja: se Pix for requisito de
conversão — e no Brasil costuma ser — ele precisa de outro caminho (boleto/
Pix por fatura, ou um gateway nacional). Isso não é limitação do código.

Produto e preço são criados na primeira necessidade e reaproveitados pela
chave `lookup_key`. Assim rodar isso duas vezes não enche a conta de
produtos repetidos.
"""
from __future__ import annotations

import os

import stripe

from .planos import MOEDA, PLANO_POR_CHAVE, Plano

class Recusado(Exception):
    """Erro que pode ser mostrado ao usuário como está."""


def configurado() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _cliente() -> stripe.StripeClient:
    chave = os.environ.get("STRIPE_SECRET_KEY")
    if not chave:
        raise Recusado("Pagamento ainda não está ligado neste servidor.")
    return stripe.StripeClient(chave)


def publica() -> str:
    return os.environ.get("STRIPE_PUBLIC_KEY", "")


def modo_teste() -> bool:
    return os.environ.get("STRIPE_SECRET_KEY", "").startswith("sk_test")


# ─────────────────────── produtos e preços ───────────────────────

def _etiqueta(plano: Plano, anual: bool) -> str:
    return f"acerolab_{plano.chave}_{'ano' if anual else 'mes'}"


def preco(plano: Plano, anual: bool = False) -> str:
    """Devolve o id do preço no Stripe, criando produto e preço se faltarem."""
    cliente = _cliente()
    etiqueta = _etiqueta(plano, anual)

    achados = cliente.v1.prices.list({
        "lookup_keys": [etiqueta], "limit": 1, "active": True})
    if achados.data:
        return achados.data[0].id

    produtos = cliente.v1.products.search({
        "query": f'metadata["plano"]:"{plano.chave}"', "limit": 1})
    if produtos.data:
        produto = produtos.data[0]
    else:
        produto = cliente.v1.products.create({
            "name": f"ACEROLAB {plano.nome}",
            "description": (f"Uma série · {plano.ritmo} · até "
                            f"{plano.videos_mes} vídeos por mês"),
            "metadata": {"plano": plano.chave},
        })

    novo = cliente.v1.prices.create({
        "product": produto.id,
        "currency": MOEDA,
        "unit_amount": plano.centavos_ano if anual else plano.centavos_mes,
        "recurring": {"interval": "year" if anual else "month"},
        "lookup_key": etiqueta,
        "metadata": {"plano": plano.chave, "ciclo": "ano" if anual else "mes"},
    })
    return novo.id


def preparar_catalogo() -> dict[str, str]:
    """Cria tudo de uma vez. Rodar isto uma vez por conta do Stripe."""
    return {
        _etiqueta(p, anual): preco(p, anual)
        for p in PLANO_POR_CHAVE.values() for anual in (False, True)
    }


# ──────────────────────────── checkout ───────────────────────────

def sessao(plano_chave: str, quantas_series: int, anual: bool,
           email: str, usuario_id: int, volta_ok: str, volta_nao: str) -> str:
    """Cria a sessão de pagamento e devolve a URL para onde mandar a pessoa."""
    cliente = _cliente()
    plano = PLANO_POR_CHAVE.get(plano_chave)
    if plano is None:
        raise Recusado("Plano desconhecido.")
    if not 1 <= quantas_series <= 50:
        raise Recusado("Escolha de 1 a 50 séries.")

    try:
        s = cliente.v1.checkout.sessions.create({
            "mode": "subscription",
            # Meios de pagamento são dinâmicos e administrados no Dashboard.
            "line_items": [{"price": preco(plano, anual), "quantity": quantas_series}],
            "customer_email": email or None,
            "locale": "pt-BR",
            "success_url": volta_ok + "?sessao={CHECKOUT_SESSION_ID}",
            "cancel_url": volta_nao,
            # O id do usuário volta no webhook: é assim que a gente sabe de
            # quem é a assinatura sem confiar no que a tela mandou.
            "client_reference_id": str(usuario_id),
            "subscription_data": {"metadata": {
                "usuario_id": str(usuario_id),
                "plano": plano.chave,
                "series": str(quantas_series),
            }},
            "metadata": {"usuario_id": str(usuario_id), "plano": plano.chave,
                         "series": str(quantas_series)},
            "integration_identifier": os.environ.get(
                "STRIPE_INTEGRATION_ID", "acerolab_checkout_qhzmdpka"),
        })
    except stripe.StripeError as erro:                       # noqa: PERF203
        raise Recusado(_humanizar(erro)) from erro
    return s.url


def ler_sessao(sessao_id: str) -> dict:
    cliente = _cliente()
    s = cliente.v1.checkout.sessions.retrieve(
        sessao_id, {"expand": ["subscription"]})
    assinatura = s.subscription
    meta = (assinatura.metadata or {}) if assinatura else {}
    return {
        "pago": s.payment_status == "paid" or s.status == "complete",
        "usuario_id": int(s.client_reference_id or 0),
        "assinatura_id": assinatura.id if assinatura else "",
        "cliente": str(s.customer or ""),
        "plano": (s.metadata or {}).get("plano", ""),
        "series": int(meta.get("series", 1)),
    }


def portal(cliente_id: str, volta_para: str) -> str:
    """Página hospedada do Stripe para trocar de plano, mudar cartão, ver
    faturas e cancelar.

    Vale mais do que parece: proporcionalidade na troca de plano, emissão de
    fatura, cancelamento e reembolso são regras chatas e cheias de detalhe
    fiscal. O Stripe já faz tudo isso e mantém em dia — refazer aqui seria
    semanas de código para chegar num lugar pior.
    """
    cliente = _cliente()
    try:
        s = cliente.v1.billing_portal.sessions.create({
            "customer": cliente_id, "return_url": volta_para})
    except stripe.StripeError as erro:
        raise Recusado(_humanizar(erro)) from erro
    return s.url


# ──────────────────────────── webhook ────────────────────────────

def evento(corpo: bytes, assinatura_cabecalho: str):
    """Confere que o aviso veio mesmo do Stripe antes de acreditar nele.

    Sem essa conferência, qualquer um que descubra a URL pode dizer que
    pagou. O segredo sai no painel do Stripe, em Developers → Webhooks.
    """
    _cliente()  # também falha fechado se o serviço estiver sem credencial
    segredo = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not segredo:
        raise Recusado("Falta STRIPE_WEBHOOK_SECRET no .env.")
    try:
        return stripe.Webhook.construct_event(corpo, assinatura_cabecalho, segredo)
    except (ValueError, stripe.SignatureVerificationError) as erro:
        raise Recusado("Aviso de pagamento com assinatura inválida.") from erro


# ──────────────────────── erro em português ──────────────────────

RECADOS: tuple[tuple[str, str], ...] = (
    ("card_declined", "O cartão foi recusado. Tente outro."),
    ("expired_card", "Esse cartão está vencido."),
    ("incorrect_cvc", "O código de segurança não confere."),
    ("insufficient_funds", "Sem limite disponível nesse cartão."),
    ("processing_error", "O banco não conseguiu processar agora. Tente de novo."),
    ("capabilities", "A conta do Stripe ainda não está habilitada a cobrar. "
                     "Complete o cadastro no painel do Stripe."),
    ("charges_enabled", "A conta do Stripe ainda não está habilitada a cobrar."),
    ("payment_method_types", "Esse meio de pagamento não vale para assinatura no Brasil."),
    ("No configuration provided", "Falta configurar o portal do cliente no painel do "
                                  "Stripe (Settings → Billing → Customer portal)."),
)


def _humanizar(erro: Exception) -> str:
    texto = str(erro)
    for pedaco, recado in RECADOS:
        if pedaco in texto:
            return recado
    return f"Não deu para concluir agora. ({texto[:200]})"
