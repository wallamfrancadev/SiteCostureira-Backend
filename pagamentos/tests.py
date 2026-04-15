from __future__ import annotations

from unittest.mock import MagicMock, patch, call
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from pedidos.models import Order
from produtos.models import Category, Product
from usuarios.models import UserProfile

from .models import Pagamento
from .exceptions import MercadoPagoAPIError
from .services import MercadoPagoService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="user1", password="senha1234"):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.get_or_create(user=user)
    return user


def get_token(client, username="user1", password="senha1234"):
    res = client.post("/api/token/", {"username": username, "password": password}, format="json")
    return res.data["access"]


def auth(client, username="user1", password="senha1234"):
    token = get_token(client, username, password)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


def make_product(name="Produto", price="100.00", stock=10):
    cat = Category.objects.get_or_create(name="Teste")[0]
    return Product.objects.create(
        name=name, description="x", price=price, stock=stock, category=cat, is_active=True
    )


ORDER_PAYLOAD = {
    "items": [],
    "shipping_address": "Rua A, 1",
    "shipping_city": "SP",
    "shipping_state": "SP",
    "shipping_cep": "01310-100",
}


def make_order_via_api(client, product, quantity=1):
    payload = {**ORDER_PAYLOAD, "items": [{"product_id": product.id, "quantity": quantity}]}
    res = client.post("/api/orders/", payload, format="json")
    return res.data


def _pix_sdk():
    sdk = MagicMock()
    sdk.payment.return_value.create.return_value = {
        "status": 201,
        "response": {
            "id": 111222333,
            "status": "pending",
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "00020101021226940014br.gov.bcb.pix",
                    "qr_code_base64": "iVBORw0KGgo=",
                    "ticket_url": "https://mercadopago.com.br/pay/111222333",
                }
            },
        },
    }
    return sdk


def _card_sdk(mp_status="approved", detail="accredited"):
    sdk = MagicMock()
    sdk.payment.return_value.create.return_value = {
        "status": 201,
        "response": {"id": 444555666, "status": mp_status, "status_detail": detail},
    }
    return sdk


def _get_sdk(mp_status="approved", payment_id="111222333"):
    sdk = MagicMock()
    sdk.payment.return_value.get.return_value = {
        "status": 200,
        "response": {
            "id": payment_id,
            "status": mp_status,
            "status_detail": "accredited",
            "external_reference": "",
        },
    }
    return sdk


_PIX_PAYLOAD = {
    "metodo": "pix",
    "payer_email": "cliente@example.com",
    "payer_first_name": "João",
    "payer_last_name": "Silva",
    "payer_cpf": "12345678901",
}

_CARD_PAYLOAD = {
    "metodo": "credit_card",
    "payer_email": "cliente@example.com",
    "payer_first_name": "João",
    "payer_last_name": "Silva",
    "payer_cpf": "12345678901",
    "token": "tok_test_abc123",
    "payment_method_id": "visa",
    "installments": 1,
}


# ---------------------------------------------------------------------------
# CreatePagamentoView — PIX
# ---------------------------------------------------------------------------

class CreatePixTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order = make_order_via_api(self.client, self.product, quantity=2)
        self.order_id = order["id"]

    @patch.object(MercadoPagoService, "_sdk")
    def test_pix_criado_com_sucesso(self, mock_sdk):
        mock_sdk.return_value = _pix_sdk()
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Pagamento.objects.count(), 1)

    @patch.object(MercadoPagoService, "_sdk")
    def test_pix_retorna_campos_obrigatorios(self, mock_sdk):
        mock_sdk.return_value = _pix_sdk()
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        for field in ("id", "id_pagamento_externo", "status", "qr_code_payload", "qr_code_image_b64", "valor_total"):
            self.assertIn(field, res.data)

    @patch.object(MercadoPagoService, "_sdk")
    def test_pix_status_inicial_pending(self, mock_sdk):
        mock_sdk.return_value = _pix_sdk()
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.data["status"], "pending")

    @patch.object(MercadoPagoService, "_sdk")
    def test_pix_salva_qr_code(self, mock_sdk):
        mock_sdk.return_value = _pix_sdk()
        self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        pag = Pagamento.objects.get()
        self.assertEqual(pag.qr_code_payload, "00020101021226940014br.gov.bcb.pix")
        self.assertEqual(pag.qr_code_image_b64, "iVBORw0KGgo=")

    @patch.object(MercadoPagoService, "_sdk")
    def test_pix_cancela_pendentes_anteriores(self, mock_sdk):
        def _pix_sdk_unique(pid):
            sdk = MagicMock()
            sdk.payment.return_value.create.return_value = {
                "status": 201,
                "response": {
                    "id": pid,
                    "status": "pending",
                    "point_of_interaction": {"transaction_data": {
                        "qr_code": "qr", "qr_code_base64": "b64", "ticket_url": "",
                    }},
                },
            }
            return sdk

        mock_sdk.return_value = _pix_sdk_unique(111)
        self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        mock_sdk.return_value = _pix_sdk_unique(222)
        self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(Pagamento.objects.filter(status="cancelled").count(), 1)
        self.assertEqual(Pagamento.objects.filter(status="pending").count(), 1)

    @patch.object(MercadoPagoService, "_sdk")
    def test_idempotency_key_enviado_ao_mp(self, mock_sdk):
        sdk_instance = _pix_sdk()
        mock_sdk.return_value = sdk_instance
        self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        _, kwargs = sdk_instance.payment.return_value.create.call_args
        headers = kwargs if kwargs else sdk_instance.payment.return_value.create.call_args[0][1]
        self.assertIn("X-Idempotency-Key", headers)


# ---------------------------------------------------------------------------
# CreatePagamentoView — Cartão
# ---------------------------------------------------------------------------

class CreateCardTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order = make_order_via_api(self.client, self.product)
        self.order_id = order["id"]

    @patch.object(MercadoPagoService, "_sdk")
    def test_cartao_aprovado_cria_pagamento(self, mock_sdk):
        mock_sdk.return_value = _card_sdk("approved")
        res = self.client.post("/api/pagamentos/", {**_CARD_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "approved")

    @patch.object(MercadoPagoService, "_sdk")
    def test_cartao_aprovado_atualiza_pedido_para_processing(self, mock_sdk):
        mock_sdk.return_value = _card_sdk("approved")
        self.client.post("/api/pagamentos/", {**_CARD_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(Order.objects.get(pk=self.order_id).status, "processing")

    @patch.object(MercadoPagoService, "_sdk")
    def test_cartao_rejected_salva_status_rejected(self, mock_sdk):
        mock_sdk.return_value = _card_sdk("rejected", "cc_rejected_insufficient_amount")
        res = self.client.post("/api/pagamentos/", {**_CARD_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["status"], "rejected")

    @patch.object(MercadoPagoService, "_sdk")
    def test_cartao_rejected_nao_muda_pedido(self, mock_sdk):
        mock_sdk.return_value = _card_sdk("rejected", "cc_rejected_insufficient_amount")
        self.client.post("/api/pagamentos/", {**_CARD_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(Order.objects.get(pk=self.order_id).status, "pending")

    @patch.object(MercadoPagoService, "_sdk")
    def test_cartao_salva_parcelas(self, mock_sdk):
        mock_sdk.return_value = _card_sdk()
        payload = {**_CARD_PAYLOAD, "order_id": self.order_id, "installments": 3}
        self.client.post("/api/pagamentos/", payload, format="json")
        self.assertEqual(Pagamento.objects.get().parcelas, 3)

    @patch.object(MercadoPagoService, "_sdk")
    def test_device_id_enviado_no_header_mp(self, mock_sdk):
        sdk_instance = _card_sdk()
        mock_sdk.return_value = sdk_instance
        payload = {**_CARD_PAYLOAD, "order_id": self.order_id, "device_id": "device-abc"}
        self.client.post("/api/pagamentos/", payload, format="json")
        call_args = sdk_instance.payment.return_value.create.call_args
        headers = call_args[0][1] if call_args[0] else call_args[1]
        self.assertEqual(headers.get("X-meli-session-id"), "device-abc")


# ---------------------------------------------------------------------------
# CreatePagamentoView — Segurança e validações
# ---------------------------------------------------------------------------

class CreatePagamentoSecurityTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order = make_order_via_api(self.client, self.product)
        self.order_id = order["id"]

    def test_requer_autenticacao(self):
        self.client.credentials()
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nao_encontra_pedido_de_outro_usuario(self):
        make_user("outro", "senha1234")
        auth(self.client, "outro")
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_pedido_inexistente_retorna_404(self):
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": 99999}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(MercadoPagoService, "_sdk")
    def test_pedido_ja_processando_retorna_400(self, mock_sdk):
        mock_sdk.return_value = _card_sdk("approved")
        self.client.post("/api/pagamentos/", {**_CARD_PAYLOAD, "order_id": self.order_id}, format="json")
        mock_sdk.return_value = _pix_sdk()
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cartao_sem_token_retorna_400(self):
        payload = {**_CARD_PAYLOAD, "order_id": self.order_id, "token": ""}
        res = self.client.post("/api/pagamentos/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cartao_sem_payment_method_id_retorna_400(self):
        payload = {**_CARD_PAYLOAD, "order_id": self.order_id, "payment_method_id": ""}
        res = self.client.post("/api/pagamentos/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_metodo_invalido_retorna_400(self):
        payload = {**_PIX_PAYLOAD, "order_id": self.order_id, "metodo": "bitcoin"}
        res = self.client.post("/api/pagamentos/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch.object(MercadoPagoService, "_sdk")
    def test_erro_mp_api_retorna_502(self, mock_sdk):
        sdk = MagicMock()
        sdk.payment.return_value.create.return_value = {
            "status": 500,
            "response": {"message": "Internal error"},
        }
        mock_sdk.return_value = sdk
        res = self.client.post("/api/pagamentos/", {**_PIX_PAYLOAD, "order_id": self.order_id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)


# ---------------------------------------------------------------------------
# PagamentoStatusView
# ---------------------------------------------------------------------------

class PagamentoStatusViewTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order_data = make_order_via_api(self.client, self.product)
        self.order = Order.objects.get(pk=order_data["id"])
        self.pagamento = Pagamento.objects.create(
            order=self.order,
            id_pagamento_externo="111222333",
            status=Pagamento.STATUS_PENDING,
            metodo_pagamento=Pagamento.METODO_PIX,
            valor_total=self.order.total,
            qr_code_payload="00020101...",
            qr_code_image_b64="iVBORw0=",
        )

    def test_requer_autenticacao(self):
        self.client.credentials()
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nao_acessa_pagamento_de_outro_usuario(self):
        make_user("outro", "senha1234")
        auth(self.client, "outro")
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_inexistente_retorna_404(self):
        res = self.client.get("/api/pagamentos/99999/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch.object(MercadoPagoService, "_sdk")
    def test_status_pending_consulta_mp(self, mock_sdk):
        mock_sdk.return_value = _get_sdk("pending", "111222333")
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_sdk.return_value.payment.return_value.get.assert_called_once_with("111222333")

    @patch.object(MercadoPagoService, "_sdk")
    def test_status_atualizado_para_approved(self, mock_sdk):
        mock_sdk.return_value = _get_sdk("approved", "111222333")
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.data["status"], "approved")
        self.pagamento.refresh_from_db()
        self.assertEqual(self.pagamento.status, Pagamento.STATUS_APPROVED)

    @patch.object(MercadoPagoService, "_sdk")
    def test_approved_atualiza_pedido_para_processing(self, mock_sdk):
        mock_sdk.return_value = _get_sdk("approved", "111222333")
        self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "processing")

    @patch.object(MercadoPagoService, "_sdk")
    def test_status_final_nao_consulta_mp(self, mock_sdk):
        self.pagamento.status = Pagamento.STATUS_APPROVED
        self.pagamento.save()
        sdk_instance = _get_sdk("approved", "111222333")
        mock_sdk.return_value = sdk_instance
        self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        sdk_instance.payment.return_value.get.assert_not_called()

    @patch.object(MercadoPagoService, "_sdk")
    def test_erro_mp_nao_quebra_response(self, mock_sdk):
        sdk = MagicMock()
        sdk.payment.return_value.get.return_value = {"status": 500, "response": {}}
        mock_sdk.return_value = sdk
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# WebhookMercadoPagoView
# ---------------------------------------------------------------------------

class WebhookTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order_data = make_order_via_api(self.client, self.product)
        self.order = Order.objects.get(pk=order_data["id"])
        self.pagamento = Pagamento.objects.create(
            order=self.order,
            id_pagamento_externo="PAY-999",
            status=Pagamento.STATUS_PENDING,
            metodo_pagamento=Pagamento.METODO_PIX,
            valor_total=self.order.total,
            qr_code_payload="00020101...",
            qr_code_image_b64="iVBORw0=",
        )
        self.client.credentials()

    def _notify(self, payment_id="PAY-999"):
        return self.client.post(
            "/api/webhook/mercadopago/",
            {"type": "payment", "data": {"id": payment_id}, "action": "payment.updated"},
            format="json",
        )

    @patch.object(MercadoPagoService, "_sdk")
    def test_webhook_retorna_200_imediatamente(self, mock_sdk):
        mock_sdk.return_value = _get_sdk("approved", "PAY-999")
        res = self._notify()
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_webhook_nao_requer_autenticacao(self):
        res = self._notify("UNKNOWN-ID")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_webhook_evento_desconhecido_retorna_200(self):
        res = self.client.post(
            "/api/webhook/mercadopago/",
            {"type": "plan", "data": {"id": "plan-1"}},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("pagamentos.views._process_webhook")
    def test_webhook_idempotente_pagamento_ja_aprovado(self, mock_process):
        self.pagamento.status = Pagamento.STATUS_APPROVED
        self.pagamento.save()
        with patch("pagamentos.views.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            self._notify("PAY-999")
        mock_thread.return_value.start.assert_called_once()
        from pagamentos.views import _process_webhook as real_fn
        with patch.object(MercadoPagoService, "buscar_pagamento") as mock_buscar:
            real_fn("PAY-999")
            mock_buscar.assert_not_called()

    @patch.object(MercadoPagoService, "buscar_pagamento")
    def test_webhook_payment_id_desconhecido_nao_quebra(self, mock_buscar):
        mock_buscar.side_effect = MercadoPagoAPIError(404, {"message": "Not found"})
        res = self._notify("ID-INEXISTENTE")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_webhook_sem_data_retorna_200(self):
        res = self.client.post("/api/webhook/mercadopago/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_webhook_aceita_formato_ipn_query_params(self):
        res = self.client.post("/api/webhook/mercadopago/?topic=payment&id=PAY-999")
        self.assertEqual(res.status_code, status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# MercadoPagoAPIError — handler de exceções
# ---------------------------------------------------------------------------

class ExceptionHandlerTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order_data = make_order_via_api(self.client, self.product)
        self.order_id = order_data["id"]

    def _post(self, mp_status_code, response_body):
        sdk = MagicMock()
        sdk.payment.return_value.create.return_value = {
            "status": mp_status_code,
            "response": response_body,
        }
        with patch.object(MercadoPagoService, "_sdk", return_value=sdk):
            return self.client.post(
                "/api/pagamentos/",
                {**_PIX_PAYLOAD, "order_id": self.order_id},
                format="json",
            )

    def test_mp_400_retorna_http_400(self):
        res = self._post(400, {"message": "Bad request", "cause": [{"code": "1000"}]})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", res.data)

    def test_mp_401_retorna_http_500(self):
        res = self._post(401, {"message": "Unauthorized"})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_mp_422_retorna_http_422(self):
        res = self._post(422, {"message": "Unprocessable", "cause": [{"code": "2034"}]})
        self.assertEqual(res.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertIn("code", res.data)

    def test_mp_500_retorna_http_502(self):
        res = self._post(500, {"message": "Internal error"})
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_resposta_de_erro_contem_detail(self):
        res = self._post(422, {"message": "Valor inválido", "cause": []})
        self.assertEqual(res.data["detail"], "Valor inválido")


# ---------------------------------------------------------------------------
# Segurança geral — endpoints privados
# ---------------------------------------------------------------------------

class EndpointSecurityTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order_data = make_order_via_api(self.client, self.product)
        self.order = Order.objects.get(pk=order_data["id"])
        self.pagamento = Pagamento.objects.create(
            order=self.order,
            id_pagamento_externo="SEC-001",
            status=Pagamento.STATUS_PENDING,
            metodo_pagamento=Pagamento.METODO_PIX,
            valor_total=self.order.total,
            qr_code_payload="x",
            qr_code_image_b64="y",
        )

    def test_post_sem_token_401(self):
        self.client.credentials()
        res = self.client.post("/api/pagamentos/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_sem_token_401(self):
        self.client.credentials()
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_outro_usuario_nao_acessa_pagamento(self):
        make_user("invasor", "senha1234")
        auth(self.client, "invasor")
        res = self.client.get(f"/api/pagamentos/{self.pagamento.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_outro_usuario_nao_paga_pedido_alheio(self):
        make_user("invasor2", "senha1234")
        auth(self.client, "invasor2")
        res = self.client.post(
            "/api/pagamentos/",
            {**_PIX_PAYLOAD, "order_id": self.order.id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_webhook_publico_sem_auth(self):
        self.client.credentials()
        res = self.client.post("/api/webhook/mercadopago/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_cpf_com_mascara_aceito(self):
        user2 = make_user("cpfuser", "senha1234")
        auth(self.client, "cpfuser")
        product2 = make_product("P2")
        order_data = make_order_via_api(self.client, product2)
        sdk = MagicMock()
        sdk.payment.return_value.create.return_value = {
            "status": 201,
            "response": {
                "id": 777,
                "status": "pending",
                "point_of_interaction": {"transaction_data": {
                    "qr_code": "qr", "qr_code_base64": "b64", "ticket_url": ""
                }},
            },
        }
        with patch.object(MercadoPagoService, "_sdk", return_value=sdk):
            payload = {**_PIX_PAYLOAD, "order_id": order_data["id"], "payer_cpf": "123.456.789-01"}
            res = self.client.post("/api/pagamentos/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        _, call_kwargs = sdk.payment.return_value.create.call_args
        body = sdk.payment.return_value.create.call_args[0][0]
        self.assertEqual(body["payer"]["identification"]["number"], "12345678901")


# ---------------------------------------------------------------------------
# Modelo Pagamento — integridade
# ---------------------------------------------------------------------------

class PagamentoModelTest(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.product = make_product()
        auth(self.client)
        order_data = make_order_via_api(self.client, self.product)
        self.order = Order.objects.get(pk=order_data["id"])

    def test_db_columns_pascalcase(self):
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT name FROM pragma_table_info('pagamentos_pagamento')")
            cols = {row[0] for row in cur.fetchall()}
        for col in ("IdPagamentoExterno", "Status", "MetodoPagamento", "ValorTotal", "DataCriacao", "DataAtualizacao"):
            self.assertIn(col, cols)

    def test_txid_unico(self):
        Pagamento.objects.create(
            order=self.order, id_pagamento_externo="UNIQUE-1",
            status=Pagamento.STATUS_PENDING, metodo_pagamento=Pagamento.METODO_PIX,
            valor_total=Decimal("50.00"), qr_code_payload="x", qr_code_image_b64="y",
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Pagamento.objects.create(
                order=self.order, id_pagamento_externo="UNIQUE-1",
                status=Pagamento.STATUS_PENDING, metodo_pagamento=Pagamento.METODO_PIX,
                valor_total=Decimal("50.00"), qr_code_payload="x", qr_code_image_b64="y",
            )

    def test_str_representation(self):
        p = Pagamento.objects.create(
            order=self.order, id_pagamento_externo="pay_abc123xyz456",
            status=Pagamento.STATUS_APPROVED, metodo_pagamento=Pagamento.METODO_CARTAO,
            valor_total=Decimal("100.00"), qr_code_payload="", qr_code_image_b64="",
        )
        self.assertIn("pay_abc123", str(p))
        self.assertIn("Aprovado", str(p))

    def test_ordenacao_mais_recente_primeiro(self):
        from django.utils import timezone as tz
        import datetime
        base = tz.now()
        for i in range(3):
            p = Pagamento(
                order=self.order, id_pagamento_externo=f"pay-{i}",
                status=Pagamento.STATUS_PENDING, metodo_pagamento=Pagamento.METODO_PIX,
                valor_total=Decimal("10.00"), qr_code_payload="", qr_code_image_b64="",
            )
            p.save()
            Pagamento.objects.filter(pk=p.pk).update(
                data_criacao=base + datetime.timedelta(seconds=i)
            )
        ids = list(Pagamento.objects.values_list("id_pagamento_externo", flat=True))
        self.assertEqual(ids, ["pay-2", "pay-1", "pay-0"])
