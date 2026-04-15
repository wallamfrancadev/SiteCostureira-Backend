from __future__ import annotations

import base64
import io
import uuid
from decimal import Decimal
from typing import TypedDict

import mercadopago
import qrcode
from django.conf import settings
from mercadopago.config.request_options import RequestOptions

from .exceptions import MercadoPagoAPIError

_DEV_MODE: bool = getattr(settings, "MP_DEV_MODE", False)


class PixResult(TypedDict):
    payment_id: str
    qr_code: str
    qr_code_base64: str
    ticket_url: str
    expiracao_segundos: int


class CardResult(TypedDict):
    payment_id: str
    status: str
    status_detail: str


class MercadoPagoService:
    @classmethod
    def _sdk(cls) -> mercadopago.SDK:
        return mercadopago.SDK(settings.MP_ACCESS_TOKEN)

    @classmethod
    def _request_options(cls, extra_headers: dict | None = None) -> RequestOptions:
        headers = {"X-Idempotency-Key": str(uuid.uuid4())}
        if extra_headers:
            headers.update(extra_headers)
        return RequestOptions(custom_headers=headers)

    @classmethod
    def _raise_if_error(cls, resp: dict) -> None:
        if resp["status"] not in (200, 201):
            raise MercadoPagoAPIError(resp["status"], resp.get("response", {}))

    @classmethod
    def _dev_pix(cls, order_id: int, valor: Decimal) -> PixResult:
        payload = f"00020126580014BR.GOV.BCB.PIX0136dev-fake-pix-{order_id}5204000053039865802BR5913DetyDev6008Sao Paulo62070503***6304FAKE"
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return PixResult(
            payment_id=f"dev_{order_id}_{uuid.uuid4().hex[:8]}",
            qr_code=payload,
            qr_code_base64=b64,
            ticket_url="",
            expiracao_segundos=3600,
        )

    @classmethod
    def _dev_card(cls) -> CardResult:
        return CardResult(
            payment_id=f"dev_{uuid.uuid4().hex[:8]}",
            status="approved",
            status_detail="accredited",
        )

    @classmethod
    def _dev_status(cls, payment_id: str) -> dict:
        return {"status": "approved", "status_detail": "accredited", "id": payment_id}

    @classmethod
    def processar_pagamento(
        cls,
        *,
        metodo: str,
        order_id: int,
        valor: Decimal,
        payer_email: str,
        payer_first_name: str = "",
        payer_last_name: str = "",
        payer_cpf: str,
        token: str = "",
        payment_method_id: str = "",
        installments: int = 1,
        device_id: str = "",
    ) -> PixResult | CardResult:
        if _DEV_MODE:
            return cls._dev_pix(order_id, valor) if metodo == "pix" else cls._dev_card()
        if metodo == "pix":
            return cls._criar_pix(
                order_id=order_id,
                valor=valor,
                payer_email=payer_email,
                payer_first_name=payer_first_name,
                payer_last_name=payer_last_name,
                payer_cpf=payer_cpf,
            )
        return cls._criar_cartao(
            order_id=order_id,
            valor=valor,
            token=token,
            payment_method_id=payment_method_id,
            installments=installments,
            payer_email=payer_email,
            payer_cpf=payer_cpf,
            device_id=device_id,
        )

    @classmethod
    def _criar_pix(
        cls,
        *,
        order_id: int,
        valor: Decimal,
        payer_email: str,
        payer_first_name: str,
        payer_last_name: str,
        payer_cpf: str,
    ) -> PixResult:
        sdk = cls._sdk()
        data = {
            "transaction_amount": float(valor),
            "description": f"Pedido #{order_id} — Dety Costureira",
            "payment_method_id": "pix",
            "payer": {
                "email": payer_email,
                "first_name": payer_first_name,
                "last_name": payer_last_name,
                "identification": {"type": "CPF", "number": payer_cpf},
            },
        }
        resp = sdk.payment().create(data, cls._request_options())
        cls._raise_if_error(resp)
        payment = resp["response"]
        tx = payment["point_of_interaction"]["transaction_data"]
        return PixResult(
            payment_id=str(payment["id"]),
            qr_code=tx["qr_code"],
            qr_code_base64=tx["qr_code_base64"],
            ticket_url=tx.get("ticket_url", ""),
            expiracao_segundos=3600,
        )

    @classmethod
    def _criar_cartao(
        cls,
        *,
        order_id: int,
        valor: Decimal,
        token: str,
        payment_method_id: str,
        installments: int,
        payer_email: str,
        payer_cpf: str,
        device_id: str,
    ) -> CardResult:
        sdk = cls._sdk()
        data = {
            "transaction_amount": float(valor),
            "token": token,
            "description": f"Pedido #{order_id} — Dety Costureira",
            "installments": installments,
            "payment_method_id": payment_method_id,
            "payer": {
                "email": payer_email,
                "identification": {"type": "CPF", "number": payer_cpf},
            },
        }
        extra = {"X-meli-session-id": device_id} if device_id else None
        resp = sdk.payment().create(data, cls._request_options(extra))
        cls._raise_if_error(resp)
        payment = resp["response"]
        return CardResult(
            payment_id=str(payment["id"]),
            status=payment["status"],
            status_detail=payment.get("status_detail", ""),
        )

    @classmethod
    def buscar_pagamento(cls, payment_id: str) -> dict:
        if _DEV_MODE:
            return cls._dev_status(payment_id)
        resp = cls._sdk().payment().get(payment_id)
        cls._raise_if_error(resp)
        return resp["response"]
