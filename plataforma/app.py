"""A plataforma — fase 1 da ficha técnica.

    .venv/bin/python -m plataforma          # sobe em http://127.0.0.1:8000

Entrar, montar série, a série propor tema, gerar e baixar. Sem conta
conectada e sem agendamento: essas dependem de auditoria do Google e do
TikTok, e ficam visíveis e desligadas no wizard de propósito.
"""
from __future__ import annotations

import json
import os
import sqlite3
from urllib.parse import quote
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from esteira.config import DATA_DIR, RAIZ, Ambiente, carregar_env

from . import (admin, catalogo, contas, fila, google_login, legal, pagamento,
               piloto, planos, seguranca, supabase, temas, uso)
from .banco import aberto, agora, inserir, preparar, um, varios

AQUI = Path(__file__).resolve().parent
AMOSTRAS = DATA_DIR / "saida" / "_amostras"

carregar_env()
preparar()

app = FastAPI(title="ACEROLAB", docs_url=None, redoc_url=None)
app.mount("/estatico", StaticFiles(directory=AQUI / "estatico"), name="estatico")
paginas = Jinja2Templates(directory=str(AQUI / "paginas"))


def url_externa(request: Request, rota: str) -> str:
    """URL canônica sem confiar em cabeçalhos de proxy enviados pelo cliente."""
    interna = request.url_for(rota)
    publica = os.environ.get("PUBLIC_URL", "").rstrip("/")
    return publica + interna.path if publica else str(interna)


@app.middleware("http")
async def protecoes_http(request: Request, call_next):
    if not seguranca.mesma_origem(request):
        return JSONResponse({"erro": "Origem da requisição recusada."}, status_code=403)
    if seguranca.excedeu_limite(request):
        return seguranca.resposta_limite()
    resposta = await call_next(request)
    for nome, valor in seguranca.HEADERS.items():
        resposta.headers.setdefault(nome, valor)
    publico_https = os.environ.get("PUBLIC_URL", "").lower().startswith("https://")
    if request.url.scheme == "https" or publico_https:
        resposta.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resposta


def moeda(valor: float) -> str:
    """R$ 1.234,56 — ponto no milhar, vírgula no centavo, como se escreve
    aqui. O `format` do Python faz o contrário e sai `R$ 1,234.56`."""
    inteiro, centavos = f"{valor:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


paginas.env.filters["moeda"] = moeda


@app.on_event("startup")
def _acordar() -> None:
    fila.iniciar()


# ───────────────────────────── sessão ────────────────────────────────

def sessao(request: Request):
    """Usuário da requisição, ou None. Não redireciona — quem exige é `exigir`."""
    with aberto() as con:
        return contas.usuario_da_sessao(con, request.cookies.get(contas.COOKIE))


def exigir(request: Request):
    usuario = sessao(request)
    if usuario is None:
        raise HTTPException(status_code=307, headers={"Location": "/entrar"})
    return usuario


@app.exception_handler(307)
async def _redirecionar(request: Request, exc: HTTPException):
    return RedirectResponse(exc.headers.get("Location", "/"), status_code=303)


def tela(request: Request, pagina: str, **ctx) -> HTMLResponse:
    """Renderiza uma página com o contexto que toda tela precisa.

    O parâmetro se chama `pagina`, não `nome`: o formulário de cadastro manda
    um campo `nome` e a colisão derrubava a tela de erro com 500.
    """
    ctx.setdefault("usuario", sessao(request))
    # o aviso de chaves fala de geração de vídeo; em tela de pagamento é ruído
    ctx.setdefault("faltando_chaves",
                   [] if pagina == "planos.html" else Ambiente().faltando())
    ctx.setdefault("tem_google", google_login.configurado())
    ctx.setdefault("eh_admin", admin.eh_admin(ctx["usuario"]))
    return paginas.TemplateResponse(request, pagina, ctx)


# ───────────────────────────── entrada ───────────────────────────────

LANDING = RAIZ / "site" / "landing.build.html"


@app.get("/", response_class=HTMLResponse)
def raiz(request: Request):
    """Quem já entrou vai pro painel; quem não entrou vê a landing.

    A landing é o arquivo pronto de `site/` — um HTML só, com fonte, imagem e
    vídeo embutidos. Vai como arquivo (e não pelo Jinja) para o navegador
    poder guardar em cache: são ~7 MB, e reprocessar isso a cada visita seria
    desperdício dos dois lados.
    """
    if sessao(request):
        return RedirectResponse("/series", status_code=303)
    if not LANDING.exists():
        # Sem a landing montada, o login vira a porta de entrada em vez de
        # devolver um 404 na raiz do site.
        return RedirectResponse("/entrar", status_code=303)
    return FileResponse(LANDING, media_type="text/html; charset=utf-8")


@app.get("/entrar", response_class=HTMLResponse)
def entrar_tela(request: Request, aba: str = "entrar", erro: str = ""):
    if sessao(request):
        return RedirectResponse("/series", status_code=303)
    return tela(request, "entrar.html", aba=aba, erro=erro)


def _com_sessao(destino: str, usuario_id: int,
                request: Request | None = None) -> RedirectResponse:
    """Abre a sessão e devolve o cookie.

    `secure` liga sozinho quando a requisição veio por HTTPS: no servidor de
    verdade o cookie nunca trafega em claro, e em `localhost` (que é http) o
    login continua funcionando durante o desenvolvimento.
    """
    with aberto() as con:
        token = contas.abrir_sessao(con, usuario_id)
    publico_https = os.environ.get("PUBLIC_URL", "").lower().startswith("https://")
    seguro = publico_https or bool(request and request.url.scheme == "https")
    resposta = RedirectResponse(destino, status_code=303)
    resposta.set_cookie(contas.COOKIE, token, httponly=True, samesite="lax",
                        secure=seguro, max_age=contas.DIAS_DE_SESSAO * 86400)
    return resposta


@app.post("/entrar")
def entrar(request: Request, email: str = Form(...), senha: str = Form(...)):
    with aberto() as con:
        novo = False
        try:
            if supabase.configurado():
                try:
                    usuario_id, novo = contas.vincular(con, supabase.entrar(email, senha))
                except supabase.Recusado:
                    usuario_id = contas.autenticar(con, email, senha)
            else:
                usuario_id = contas.autenticar(con, email, senha)
        except (contas.Recusado, supabase.Recusado) as erro:
            return tela(request, "entrar.html", aba="entrar", erro=str(erro), email=email)
    return _com_sessao("/comecar" if novo else "/series", usuario_id, request)


@app.post("/cadastrar")
def cadastrar(request: Request, email: str = Form(...), senha: str = Form(...),
              nome: str = Form(""), aceite: str = Form("")):
    # Conferir aqui também: caixa marcada só no navegador não prova nada, e o
    # aceite é o que sustenta a cobrança depois.
    if not aceite:
        return tela(request, "entrar.html", aba="cadastrar", email=email, nome=nome,
                    erro="Marque que você leu e aceita os termos e a política de privacidade.")

    with aberto() as con:
        try:
            if supabase.configurado():
                pessoa = supabase.cadastrar(email, senha, nome)
                if not pessoa.get("confirmado"):
                    # Conta criada, mas sem sessão: entrar agora daria acesso a
                    # quem ainda não provou que é dono do e-mail.
                    return tela(request, "entrar.html", aba="entrar", email=email,
                                recado="Conta criada. Abra o e-mail que acabamos de "
                                       "enviar e clique no link para confirmar — "
                                       "depois é só entrar aqui.")
                usuario_id, _ = contas.vincular(con, pessoa)
            else:
                usuario_id = contas.cadastrar(con, email, senha, nome)
        except (contas.Recusado, supabase.Recusado) as erro:
            return tela(request, "entrar.html", aba="cadastrar", erro=str(erro),
                        email=email, nome=nome)
    return _com_sessao("/comecar", usuario_id, request)


# ─────────────────────── entrar com o Google ─────────────────────────

ESTADO_GOOGLE = "acerolab_estado_google"


@app.get("/entrar/google")
def entrar_google(request: Request):
    """Manda a pessoa pro Google, guardando o estado (anti-CSRF) aqui."""
    if not google_login.configurado():
        return RedirectResponse(
            "/entrar?erro=" + quote("Login com Google ainda não está ligado neste servidor."),
            status_code=303)

    estado = google_login.novo_estado()
    volta = url_externa(request, "entrar_retorno")
    resposta = RedirectResponse(google_login.url_login(volta, estado), status_code=303)
    # dura poucos minutos: é só a ida e a volta do Google
    resposta.set_cookie(ESTADO_GOOGLE, estado, httponly=True, samesite="lax",
                        max_age=600, path="/entrar")
    return resposta


@app.get("/entrar/retorno", name="entrar_retorno")
def entrar_retorno(request: Request, code: str = "", state: str = "",
                   error_description: str = ""):
    if error_description:
        return RedirectResponse("/entrar?erro=" + quote(error_description[:200]),
                                status_code=303)

    estado_esperado = request.cookies.get(ESTADO_GOOGLE)
    if not code or not state or state != estado_esperado:
        return RedirectResponse(
            "/entrar?erro=" + quote("A volta do Google expirou. Tente de novo."),
            status_code=303)

    try:
        volta = url_externa(request, "entrar_retorno")
        pessoa = google_login.trocar_codigo(code, volta)
        with aberto() as con:
            usuario_id, novo = contas.vincular(con, pessoa)
    except (contas.Recusado, google_login.Recusado) as erro:
        return RedirectResponse("/entrar?erro=" + quote(str(erro)[:200]), status_code=303)

    resposta = _com_sessao("/comecar" if novo else "/series", usuario_id, request)
    resposta.delete_cookie(ESTADO_GOOGLE, path="/entrar")
    return resposta


@app.post("/reenviar")
def reenviar(request: Request, email: str = Form(...)):
    if supabase.configurado():
        supabase.reenviar_confirmacao(email)
    return tela(request, "entrar.html", aba="entrar", email=email,
                recado="Se a conta existir e ainda não estiver confirmada, "
                       "o link foi reenviado.")


@app.post("/esqueci")
def esqueci(request: Request, email: str = Form(...)):
    """Manda o e-mail de redefinição. A resposta é sempre a mesma, exista a
    conta ou não — dizer qual e-mail existe entrega a base de clientes."""
    if supabase.configurado():
        supabase.recuperar(email, url_externa(request, "entrar_tela"))
    return tela(request, "entrar.html", aba="entrar", email=email,
                recado="Se existir conta com esse e-mail, o link de nova senha já saiu.")


@app.get("/termos", response_class=HTMLResponse)
@app.get("/privacidade", response_class=HTMLResponse)
def documento(request: Request):
    chave = request.url.path.strip("/")
    doc = legal.DOCUMENTOS.get(chave)
    if doc is None:
        raise HTTPException(404)
    return paginas.TemplateResponse(request, "legal.html", {
        "doc": doc, "atualizado": legal.ATUALIZADO, "revisado": legal.REVISADO,
    })


# ─────────────────────────── planos e pagamento ──────────────────────

def assinatura_de(con, usuario_id: int):
    return uso.assinatura_ativa(con, usuario_id)


@app.get("/planos", response_class=HTMLResponse)
def tela_planos(request: Request, usuario=Depends(exigir), erro: str = ""):
    with aberto() as con:
        atual = assinatura_de(con, usuario["id"])
    return tela(request, "planos.html", planos=planos, atual=atual, erro=erro,
                teste=pagamento.modo_teste())


@app.post("/assinar")
async def assinar(request: Request, usuario=Depends(exigir)):
    f = await request.form()
    try:
        destino = pagamento.sessao(
            plano_chave=str(f.get("plano", "")),
            quantas_series=int(str(f.get("series", "1")) or 1),
            anual=bool(f.get("anual")),
            email=usuario["email"],
            usuario_id=int(usuario["id"]),
            volta_ok=url_externa(request, "pagamento_ok"),
            volta_nao=url_externa(request, "tela_planos"),
        )
    except (pagamento.Recusado, ValueError) as erro:
        return RedirectResponse("/planos?erro=" + quote(str(erro)[:180]), status_code=303)
    return RedirectResponse(destino, status_code=303)


def guardar_assinatura(con, usuario_id: int, stripe_id: str, plano: str,
                       series: int, estado: str = "ativa", cliente: str = "") -> None:
    """Grava ou atualiza. O id do Stripe é único, então reprocessar o mesmo
    aviso duas vezes não cria assinatura duplicada — webhook repete."""
    con.execute("""
        INSERT INTO assinaturas (usuario_id, stripe_id, stripe_cliente, plano,
                                 series, estado, criada_em)
             VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(stripe_id) DO UPDATE SET
             plano=excluded.plano, series=excluded.series, estado=excluded.estado,
             stripe_cliente=CASE WHEN excluded.stripe_cliente != ''
                                 THEN excluded.stripe_cliente
                                 ELSE assinaturas.stripe_cliente END
    """, (usuario_id, stripe_id, cliente, plano, series, estado, agora()))


@app.get("/pagamento/ok", name="pagamento_ok", response_class=HTMLResponse)
def pagamento_ok(request: Request, sessao: str = "", usuario=Depends(exigir)):
    """Volta do checkout. Confirma na hora para a tela não mentir enquanto o
    webhook não chega — mas quem manda de verdade continua sendo o webhook."""
    if sessao:
        try:
            dados = pagamento.ler_sessao(sessao)
            if dados["usuario_id"] != int(usuario["id"]):
                raise HTTPException(403, "Esta sessão de pagamento pertence a outra conta.")
            if dados["pago"] and dados["assinatura_id"]:
                with aberto() as con:
                    guardar_assinatura(con, int(usuario["id"]), dados["assinatura_id"],
                                       dados["plano"], dados["series"],
                                       cliente=dados["cliente"])
        except HTTPException:
            raise
        except Exception:                                    # noqa: BLE001
            pass       # o webhook resolve; a tela não trava por causa disso
    return RedirectResponse("/series?assinou=1", status_code=303)


@app.get("/assinatura/gerenciar")
def gerenciar(request: Request, usuario=Depends(exigir)):
    """Manda para o portal do Stripe: trocar de plano, mudar cartão, ver
    faturas, cancelar. Tudo isso lá, e não aqui, porque proporcionalidade e
    emissão de fatura são regras que o Stripe já mantém em dia."""
    with aberto() as con:
        atual = assinatura_de(con, usuario["id"])
    if atual is None or not atual["stripe_cliente"]:
        return RedirectResponse("/planos", status_code=303)
    try:
        destino = pagamento.portal(atual["stripe_cliente"],
                                   url_externa(request, "tela_planos"))
    except pagamento.Recusado as erro:
        return RedirectResponse("/planos?erro=" + quote(str(erro)[:180]), status_code=303)
    return RedirectResponse(destino, status_code=303)


@app.post("/webhooks/stripe")
async def webhook(request: Request, stripe_signature: str = Header("")):
    corpo = await request.body()
    try:
        evento = pagamento.evento(corpo, stripe_signature)
    except pagamento.Recusado as erro:
        raise HTTPException(400, str(erro))

    tipo = evento["type"]
    dado = evento["data"]["object"]

    if tipo in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        usuario_id = int(dado.get("client_reference_id") or 0)
        assinatura = dado.get("subscription")
        if usuario_id and assinatura and dado.get("payment_status") != "unpaid":
            with aberto() as con:
                guardar_assinatura(con, usuario_id, assinatura,
                                   (dado.get("metadata") or {}).get("plano", ""),
                                   int((dado.get("metadata") or {}).get("series", 1)),
                                   cliente=str(dado.get("customer") or ""))

    elif tipo in ("customer.subscription.created", "customer.subscription.updated",
                  "customer.subscription.deleted"):
        meta = dado.get("metadata") or {}
        estado = {"active": "ativa", "trialing": "ativa",
                  "past_due": "vencida", "unpaid": "vencida"}.get(
                      dado.get("status", ""), "cancelada")
        with aberto() as con:
            con.execute("UPDATE assinaturas SET estado=? WHERE stripe_id=?",
                        (estado, dado.get("id", "")))
            if meta.get("usuario_id") and estado == "ativa":
                guardar_assinatura(con, int(meta["usuario_id"]), dado["id"],
                                   meta.get("plano", ""), int(meta.get("series", 1)))

    elif tipo in ("invoice.paid", "invoice.payment_failed"):
        # A versão nova da API moveu a assinatura para `parent`; aceitamos
        # também o campo antigo para atravessar a migração sem perder evento.
        assinatura = dado.get("subscription")
        if not assinatura:
            detalhes = ((dado.get("parent") or {}).get("subscription_details") or {})
            assinatura = detalhes.get("subscription")
        if isinstance(assinatura, dict):
            assinatura = assinatura.get("id")
        if assinatura:
            with aberto() as con:
                con.execute("UPDATE assinaturas SET estado=? WHERE stripe_id=?",
                            ("ativa" if tipo == "invoice.paid" else "vencida",
                             str(assinatura)))

    elif tipo == "checkout.session.async_payment_failed":
        assinatura = dado.get("subscription")
        if assinatura:
            with aberto() as con:
                con.execute("UPDATE assinaturas SET estado='vencida' WHERE stripe_id=?",
                            (str(assinatura),))

    return JSONResponse({"recebido": True})


@app.post("/sair")
def sair(request: Request):
    token = request.cookies.get(contas.COOKIE)
    if token:
        with aberto() as con:
            contas.fechar_sessao(con, token)
    resposta = RedirectResponse("/entrar", status_code=303)
    resposta.delete_cookie(contas.COOKIE)
    return resposta


# ───────────────────────────── começo ────────────────────────────────

@app.get("/comecar", response_class=HTMLResponse)
def comecar(request: Request, usuario=Depends(exigir)):
    return tela(request, "comecar.html")


# ───────────────────────────── admin ─────────────────────────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_painel(request: Request, usuario=Depends(exigir)):
    if not admin.eh_admin(usuario):
        raise HTTPException(status_code=404)
    with aberto() as con:
        return tela(request, "admin.html",
                    resumo=admin.resumo(con),
                    cadastros=admin.cadastros_por_dia(con),
                    usuarios=admin.usuarios_com_uso(con),
                    fila=admin.fila_saude(con),
                    erros=admin.erros_recentes(con),
                    assinaturas=admin.assinaturas_resumo(con))


@app.get("/admin/usuarios/{usuario_id}", response_class=HTMLResponse)
def admin_usuario(request: Request, usuario_id: int, usuario=Depends(exigir)):
    if not admin.eh_admin(usuario):
        raise HTTPException(status_code=404)
    with aberto() as con:
        detalhe = admin.usuario_detalhe(con, usuario_id)
        if detalhe is None:
            raise HTTPException(status_code=404)
        return tela(request, "admin_usuario.html", **detalhe)


# ───────────────────────────── séries ────────────────────────────────

@app.get("/series", response_class=HTMLResponse)
def series(request: Request, usuario=Depends(exigir)):
    with aberto() as con:
        linhas = varios(con, """
            SELECT s.*,
                   (SELECT COUNT(*) FROM videos v
                     WHERE v.serie_id = s.id AND v.estado='pronto') AS prontos,
                   (SELECT COUNT(*) FROM temas t
                     WHERE t.serie_id = s.id AND t.estado='proposto') AS pautas,
                   -- os três últimos prontos viram o mosaico de capa do cartão
                   (SELECT group_concat(id) FROM
                       (SELECT id FROM videos
                         WHERE serie_id = s.id AND estado='pronto'
                         ORDER BY id DESC LIMIT 3)) AS capas
              FROM series s
             WHERE s.usuario_id = ? AND s.arquivada = 0
             ORDER BY s.id DESC
        """, usuario["id"])
    return tela(request, "series.html", series=linhas, cat=catalogo)


@app.get("/series/nova", response_class=HTMLResponse)
def serie_nova(request: Request, usuario=Depends(exigir)):
    return tela(request, "wizard.html", cat=catalogo,
                musicas=catalogo.musicas_disponiveis())


@app.post("/series/nova")
async def serie_criar(request: Request, usuario=Depends(exigir)):
    f = await request.form()
    nicho = str(f.get("nicho", "")).strip()
    personalizado = str(f.get("nicho_personalizado", "")).strip()

    if nicho == "personalizado":
        if not personalizado:
            raise HTTPException(400, "Descreva o nicho personalizado.")
        nicho_texto = personalizado
    else:
        conhecido = catalogo.NICHO_POR_CHAVE.get(nicho)
        if conhecido is None:
            raise HTTPException(400, "Nicho inválido.")
        nicho_texto = conhecido.prompt

    musicas = [m for m in f.getlist("musicas") if isinstance(m, str)]
    nome = str(f.get("nome", "")).strip() or (
        catalogo.NICHO_POR_CHAVE[nicho].nome if nicho in catalogo.NICHO_POR_CHAVE
        else "Minha série")
    modo = str(f.get("modo", "automatico"))
    if modo not in {"automatico", "imagem", "video"}:
        modo = "automatico"
    modelo_video = str(f.get("modelo_video", "wan"))
    if modelo_video not in {"wan", "seedance", "kling"}:
        modelo_video = "wan"
    piloto_ativo = str(f.get("piloto", "0")) == "1"
    frequencia = str(f.get("frequencia", "semanal"))
    if frequencia not in piloto.INTERVALOS:
        frequencia = "semanal"

    with aberto() as con:
        # A conferência e a criação precisam ser uma operação só: duas
        # abas abertas não podem ultrapassar o limite ao mesmo tempo.
        con.execute("BEGIN IMMEDIATE")
        try:
            uso.conferir_nova_serie(con, int(usuario["id"]))
        except uso.Recusado as erro:
            con.rollback()
            return RedirectResponse("/planos?erro=" + quote(str(erro)), status_code=303)
        serie_id = inserir(con, """
            INSERT INTO series (usuario_id, nome, nicho, nicho_texto, idioma, voz,
                                musicas, estilo, legenda, duracao, modo, modelo_video,
                                piloto_ativo, frequencia, proxima_geracao, criada_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, usuario["id"], nome, nicho, nicho_texto,
             str(f.get("idioma", "pt-BR")), str(f.get("voz", "")),
             json.dumps(musicas), str(f.get("estilo", "cinematografico")),
             str(f.get("legenda", "traco-forte")), str(f.get("duracao", "curto")),
             modo, modelo_video, int(piloto_ativo), frequencia,
             agora() if piloto_ativo else "",
             agora())
        con.commit()
    return RedirectResponse(f"/series/{serie_id}", status_code=303)


@app.get("/series/{serie_id}", response_class=HTMLResponse)
def serie(request: Request, serie_id: int, erro: str = "", usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, "SELECT * FROM series WHERE id=? AND usuario_id=?",
                   serie_id, usuario["id"])
        if linha is None:
            raise HTTPException(404, "Série não encontrada.")
        pautas = varios(con, """
            SELECT * FROM temas WHERE serie_id=? AND estado='proposto'
             ORDER BY id DESC
        """, serie_id)
        videos = varios(con, """
            SELECT * FROM videos WHERE serie_id=? ORDER BY id DESC LIMIT 40
        """, serie_id)
    return tela(request, "serie.html", serie=linha, pautas=pautas,
                videos=videos, cat=catalogo, piloto=piloto, erro=erro)


@app.post("/series/{serie_id}/direcao")
async def serie_direcao(request: Request, serie_id: int, usuario=Depends(exigir)):
    f = await request.form()
    modo = str(f.get("modo", "automatico"))
    modelo = str(f.get("modelo_video", "wan"))
    frequencia = str(f.get("frequencia", "semanal"))
    ativo = str(f.get("piloto", "0")) == "1"
    if modo not in {"automatico", "imagem", "video"}:
        raise HTTPException(400, "Motor visual inválido.")
    if modelo not in {"wan", "seedance", "kling"}:
        raise HTTPException(400, "Modelo de vídeo inválido.")
    with aberto() as con:
        linha = um(con, "SELECT id FROM series WHERE id=? AND usuario_id=?",
                   serie_id, usuario["id"])
        if linha is None:
            raise HTTPException(404, "Série não encontrada.")
        con.execute("UPDATE series SET modo=?, modelo_video=? WHERE id=?",
                    (modo, modelo, serie_id))
        piloto.configurar(con, serie_id, ativo, frequencia)
    return RedirectResponse(f"/series/{serie_id}", status_code=303)


@app.post("/series/{serie_id}/pautas")
def serie_pautas(request: Request, serie_id: int, usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, "SELECT * FROM series WHERE id=? AND usuario_id=?",
                   serie_id, usuario["id"])
        if linha is None:
            raise HTTPException(404, "Série não encontrada.")
        try:
            temas.propor(con, linha)
        except Exception as erro:                            # noqa: BLE001
            return RedirectResponse(f"/series/{serie_id}?erro={erro}", status_code=303)
    return RedirectResponse(f"/series/{serie_id}", status_code=303)


@app.post("/series/{serie_id}/gerar")
async def serie_gerar(request: Request, serie_id: int, usuario=Depends(exigir)):
    f = await request.form()
    tema_id = f.get("tema_id")
    with aberto() as con:
        con.execute("BEGIN IMMEDIATE")
        linha = um(con, "SELECT id FROM series WHERE id=? AND usuario_id=?",
                   serie_id, usuario["id"])
        if linha is None:
            raise HTTPException(404, "Série não encontrada.")
        try:
            uso.conferir_novo_video(con, int(usuario["id"]))
        except uso.Recusado as erro:
            con.rollback()
            return RedirectResponse(f"/series/{serie_id}?erro=" + quote(str(erro)),
                                    status_code=303)
        tema_num = int(tema_id) if tema_id else None
        if tema_num is not None and um(con, """
            SELECT id FROM temas WHERE id=? AND serie_id=? AND estado='proposto'
        """, tema_num, serie_id) is None:
            raise HTTPException(404, "Pauta não encontrada nesta série.")
        inserir(con, """
            INSERT INTO videos (serie_id, usuario_id, tema_id, criado_em)
            VALUES (?,?,?,?)
        """, serie_id, usuario["id"], tema_num, agora())
        con.commit()
    return RedirectResponse(f"/series/{serie_id}", status_code=303)


@app.post("/pautas/{tema_id}/descartar")
def descartar(request: Request, tema_id: int, usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, """
            SELECT t.id, t.serie_id FROM temas t JOIN series s ON s.id = t.serie_id
             WHERE t.id=? AND s.usuario_id=?
        """, tema_id, usuario["id"])
        if linha is None:
            raise HTTPException(404, "Pauta não encontrada.")
        con.execute("UPDATE temas SET estado='descartado' WHERE id=?", (tema_id,))
    return RedirectResponse(f"/series/{linha['serie_id']}", status_code=303)


# ───────────────────────────── vídeos ────────────────────────────────

@app.get("/videos", response_class=HTMLResponse)
def videos(request: Request, usuario=Depends(exigir)):
    with aberto() as con:
        linhas = varios(con, """
            SELECT v.*, s.nome AS serie_nome
              FROM videos v JOIN series s ON s.id = v.serie_id
             WHERE v.usuario_id = ? ORDER BY v.id DESC LIMIT 120
        """, usuario["id"])
    return tela(request, "videos.html", videos=linhas)


@app.get("/videos/{video_id}/baixar")
def baixar(request: Request, video_id: int, usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, "SELECT * FROM videos WHERE id=? AND usuario_id=?",
                   video_id, usuario["id"])
    if linha is None or linha["estado"] != "pronto":
        raise HTTPException(404, "Vídeo não disponível.")
    arquivo = Path(linha["arquivo"])
    if not arquivo.exists():
        raise HTTPException(410, "O arquivo desse vídeo não está mais no disco.")
    nome = (linha["titulo"] or f"acerolab-{video_id}")[:60]
    limpo = "".join(c if c.isalnum() or c in " -_" else "" for c in nome).strip()
    return FileResponse(arquivo, media_type="video/mp4",
                        filename=f"{limpo or f'acerolab-{video_id}'}.mp4")


@app.get("/videos/{video_id}/capa")
def capa(request: Request, video_id: int, usuario=Depends(exigir)):
    """Quadro do vídeo, para a grade não virar retângulo cinza."""
    with aberto() as con:
        linha = um(con, "SELECT pasta FROM videos WHERE id=? AND usuario_id=?",
                   video_id, usuario["id"])
    if linha is None or not linha["pasta"]:
        raise HTTPException(404)
    arquivo = Path(linha["pasta"]) / "capa.webp"
    if not arquivo.exists():
        raise HTTPException(404)
    return FileResponse(arquivo, media_type="image/webp",
                        headers={"Cache-Control": "private, max-age=86400"})


@app.get("/videos/{video_id}/ver")
def ver(request: Request, video_id: int, usuario=Depends(exigir)):
    """O MP4 em si, para tocar dentro da página em vez de só baixar."""
    with aberto() as con:
        linha = um(con, "SELECT arquivo, estado FROM videos WHERE id=? AND usuario_id=?",
                   video_id, usuario["id"])
    if linha is None or linha["estado"] != "pronto":
        raise HTTPException(404)
    arquivo = Path(linha["arquivo"])
    if not arquivo.exists():
        raise HTTPException(410, "O arquivo desse vídeo não está mais no disco.")
    return FileResponse(arquivo, media_type="video/mp4")


def _midias_da_pasta(pasta: Path, quantas: int) -> list[Path | None]:
    """Recupera exatamente a mídia usada em cada cena, inclusive no híbrido."""
    arquivo_lista = pasta / "midias.json"
    nomes: list[str] = []
    if arquivo_lista.exists():
        try:
            dados = json.loads(arquivo_lista.read_text(encoding="utf-8"))
            if isinstance(dados, list):
                nomes = [Path(str(nome)).name for nome in dados]
        except (OSError, json.JSONDecodeError):
            nomes = []
    resultado: list[Path | None] = []
    cenas = pasta / "cenas"
    for indice in range(quantas):
        candidato = cenas / nomes[indice] if indice < len(nomes) else None
        if candidato is None or not candidato.exists():
            opcoes = sorted(cenas.glob(f"cena_{indice:02d}.*"),
                            key=lambda p: p.suffix.lower() not in {".mp4", ".mov", ".webm"})
            candidato = opcoes[0] if opcoes else None
        resultado.append(candidato)
    return resultado


@app.get("/videos/{video_id}/estudio", response_class=HTMLResponse)
def estudio(request: Request, video_id: int, usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, """
            SELECT v.*, s.nome AS serie_nome, s.modo
              FROM videos v JOIN series s ON s.id=v.serie_id
             WHERE v.id=? AND v.usuario_id=?
        """, video_id, usuario["id"])
    if linha is None or linha["estado"] != "pronto" or not linha["pasta"]:
        raise HTTPException(404, "Vídeo não disponível no estúdio.")
    roteiro_arquivo = Path(linha["pasta"]) / "roteiro.json"
    try:
        roteiro = json.loads(roteiro_arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(410, "A direção deste vídeo não está mais no disco.")
    cenas = roteiro.get("cenas", []) if isinstance(roteiro, dict) else []
    midias = _midias_da_pasta(Path(linha["pasta"]), len(cenas))
    storyboard = []
    for indice, (cena, midia) in enumerate(zip(cenas, midias)):
        item = dict(cena) if isinstance(cena, dict) else {}
        item.update({
            "indice": indice,
            "tem_midia": midia is not None,
            "video": bool(midia and midia.suffix.lower() in {".mp4", ".mov", ".webm"}),
        })
        storyboard.append(item)
    return tela(request, "estudio.html", video=linha, roteiro=roteiro,
                storyboard=storyboard)


@app.get("/videos/{video_id}/cenas/{indice}")
def cena_midia(request: Request, video_id: int, indice: int,
               usuario=Depends(exigir)):
    with aberto() as con:
        linha = um(con, "SELECT pasta FROM videos WHERE id=? AND usuario_id=?",
                   video_id, usuario["id"])
    if linha is None or not linha["pasta"] or indice < 0:
        raise HTTPException(404)
    roteiro = Path(linha["pasta"]) / "roteiro.json"
    try:
        quantas = len(json.loads(roteiro.read_text(encoding="utf-8")).get("cenas", []))
    except (OSError, json.JSONDecodeError, AttributeError):
        raise HTTPException(404)
    if indice >= quantas:
        raise HTTPException(404)
    midia = _midias_da_pasta(Path(linha["pasta"]), quantas)[indice]
    if midia is None or not midia.exists():
        raise HTTPException(404)
    tipos = {".mp4": "video/mp4", ".webm": "video/webm", ".png": "image/png",
             ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    return FileResponse(midia, media_type=tipos.get(midia.suffix.lower(), "application/octet-stream"),
                        headers={"Cache-Control": "private, max-age=86400"})


@app.get("/api/estado")
def estado(request: Request, usuario=Depends(exigir)):
    """Progresso da fila, para a tela atualizar sem recarregar."""
    with aberto() as con:
        linhas = varios(con, """
            SELECT id, estado, etapa, titulo, custo_reais, erro
              FROM videos WHERE usuario_id=? AND estado IN ('na_fila','gerando')
        """, usuario["id"])
    return JSONResponse({"videos": [dict(l) for l in linhas]})


# ─────────────────────── prévia de voz (o "play") ────────────────────

@app.get("/api/voz/{voz_id}")
def previa_voz(request: Request, voz_id: str, idioma: str = "pt-BR",
               usuario=Depends(exigir)):
    """Amostra da voz, gerada uma vez e guardada em disco.

    É o botão de play que a ClipShort tem e o AutoShortz não. Custa uma
    frase curta por voz — depois disso é arquivo estático.
    """
    if voz_id not in catalogo.VOZ_POR_ID:
        raise HTTPException(404, "Voz desconhecida.")
    if Ambiente().elevenlabs is None:
        raise HTTPException(503, "Falta a chave da ElevenLabs no .env.")

    AMOSTRAS.mkdir(parents=True, exist_ok=True)
    destino = AMOSTRAS / f"{voz_id}_{idioma}.mp3"
    if not destino.exists():
        import os
        texto = catalogo.AMOSTRA.get(idioma, catalogo.AMOSTRA["pt-BR"])
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voz_id}",
            json={"text": texto, "model_id": "eleven_flash_v2_5",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"],
                     "accept": "audio/mpeg"},
            timeout=60,
        )
        if r.status_code != 200:
            raise HTTPException(502, f"ElevenLabs recusou: {r.status_code}")
        destino.write_bytes(r.content)
    return FileResponse(destino, media_type="audio/mpeg")


@app.get("/api/musica/{arquivo}")
def previa_musica(request: Request, arquivo: str, usuario=Depends(exigir)):
    escolhida = next((m for m in catalogo.MUSICAS_CATALOGO if m.arquivo == arquivo), None)
    if escolhida is None or not escolhida.existe:
        raise HTTPException(404, "Música não encontrada.")
    return FileResponse(escolhida.caminho, media_type="audio/mpeg")
