from __future__ import annotations

import os
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from starlette.requests import Request

from plataforma import pagamento, seguranca, uso


def requisicao(method: str = "POST", path: str = "/series/1/gerar",
               headers: dict[str, str] | None = None) -> Request:
    cabecalhos = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({
        "type": "http", "method": method, "scheme": "https",
        "server": ("acerolab.test", 443), "path": path, "query_string": b"",
        "headers": cabecalhos, "client": ("127.0.0.1", 1234),
    })


class SegurancaTest(unittest.TestCase):
    def test_csp_aceita_midias_e_fontes_embutidas_da_landing(self):
        csp = seguranca.HEADERS["Content-Security-Policy"]
        self.assertIn("media-src 'self' data: blob:", csp)
        self.assertIn("font-src 'self' data:", csp)

    def test_recusa_post_de_outro_site(self):
        req = requisicao(headers={"origin": "https://malicioso.test",
                                  "host": "acerolab.test"})
        self.assertFalse(seguranca.mesma_origem(req))

    def test_aceita_post_da_mesma_origem(self):
        req = requisicao(headers={"origin": "https://acerolab.test",
                                  "host": "acerolab.test"})
        self.assertTrue(seguranca.mesma_origem(req))

    def test_webhook_nao_depende_de_origin(self):
        self.assertTrue(seguranca.mesma_origem(
            requisicao(path="/webhooks/stripe", headers={"host": "acerolab.test"})))


class UsoTest(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript("""
            CREATE TABLE assinaturas (id INTEGER PRIMARY KEY, usuario_id INTEGER,
              plano TEXT, series INTEGER, estado TEXT);
            CREATE TABLE series (id INTEGER PRIMARY KEY, usuario_id INTEGER,
              arquivada INTEGER DEFAULT 0);
            CREATE TABLE videos (id INTEGER PRIMARY KEY, usuario_id INTEGER,
              criado_em TEXT, estado TEXT);
        """)

    def tearDown(self):
        self.con.close()

    def test_exige_assinatura(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(uso.Recusado):
                uso.exigir_assinatura(self.con, 1)

    def test_respeita_limite_de_series(self):
        self.con.execute("INSERT INTO assinaturas VALUES (1,1,'inicial',1,'ativa')")
        self.con.execute("INSERT INTO series VALUES (1,1,0)")
        with self.assertRaises(uso.Recusado):
            uso.conferir_nova_serie(self.con, 1)

    def test_falha_nao_consumiu_franquia(self):
        self.con.execute("INSERT INTO assinaturas VALUES (1,1,'inicial',1,'ativa')")
        for n in range(13):
            self.con.execute("INSERT INTO videos VALUES (?,?,?,?)",
                             (n + 1, 1, "2099-01-01T00:00:00", "falhou"))
        resultado = uso.conferir_novo_video(self.con, 1)
        self.assertEqual(resultado["usados"], 0)

    def test_fila_tem_limite(self):
        self.con.execute("INSERT INTO assinaturas VALUES (1,1,'inicial',1,'ativa')")
        for n in range(3):
            self.con.execute("INSERT INTO videos VALUES (?,?,?,?)",
                             (n + 1, 1, "2099-01-01T00:00:00", "na_fila"))
        with self.assertRaises(uso.Recusado):
            uso.conferir_novo_video(self.con, 1)


class PagamentoTest(unittest.TestCase):
    def test_checkout_usa_metodos_dinamicos_e_metadados(self):
        recebido = {}

        class Sessoes:
            @staticmethod
            def create(parametros):
                recebido.update(parametros)
                return SimpleNamespace(url="https://checkout.stripe.test/sessao")

        falso = SimpleNamespace(v1=SimpleNamespace(
            checkout=SimpleNamespace(sessions=Sessoes())))
        with patch.object(pagamento, "_cliente", return_value=falso), \
             patch.object(pagamento, "preco", return_value="price_teste"):
            url = pagamento.sessao("inicial", 2, False, "pessoa@example.com", 7,
                                   "https://acerolab.test/ok", "https://acerolab.test/nao")

        self.assertEqual(url, "https://checkout.stripe.test/sessao")
        self.assertNotIn("payment_method_types", recebido)
        self.assertEqual(recebido["metadata"]["series"], "2")
        self.assertEqual(recebido["subscription_data"]["metadata"]["usuario_id"], "7")
        self.assertTrue(recebido["integration_identifier"].startswith("acerolab_checkout_"))


if __name__ == "__main__":
    unittest.main()
