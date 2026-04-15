from __future__ import annotations

import logging
import threading

from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from pedidos.models import Order
from .exceptions import MercadoPagoAPIError
from .models import Pagamento
from .serializers import CreatePagamentoSerializer, PagamentoSerializer
from .services import MercadoPagoService

logger = logging.getLogger(__name__)

_MP_FINAL_STATUSES: frozenset[str] = frozenset(
    {"approved", "rejected", "cancelled", "refunded", "charged_back", "in_mediation"}
)

_MP_STATUS_MAP: dict[str, str] = {
    "approved": Pagamento.STATUS_APPROVED,
    "pending": Pagamento.STATUS_PENDING,
    "authorized": Pagamento.STATUS_PENDING,
    "in_process": Pagamento.STATUS_IN_PROCESS,
    "in_mediation": Pagamento.STATUS_IN_MEDIATION,
    "rejected": Pagamento.STATUS_REJECTED,
    "cancelled": Pagamento.STATUS_CANCELLED,
    "refunded": Pagamento.STATUS_REFUNDED,
    "charged_back": Pagamento.STATUS_REFUNDED,
}


class CreatePagamentoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: object) -> Response:
        serializer = CreatePagamentoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        try:
            order = Order.objects.get(pk=d["order_id"], user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "Pedido não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if order.status != "pending":
            return Response(
                {"detail": "Apenas pedidos pendentes podem ser pagos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Pagamento.objects.filter(order=order, status=Pagamento.STATUS_PENDING).update(
            status=Pagamento.STATUS_CANCELLED
        )

        payer_cpf = d["payer_cpf"].replace(".", "").replace("-", "").replace("/", "")

        try:
            result = MercadoPagoService.processar_pagamento(
                metodo=d["metodo"],
                order_id=order.id,
                valor=order.total,
                payer_email=d["payer_email"],
                payer_first_name=d["payer_first_name"],
                payer_last_name=d["payer_last_name"],
                payer_cpf=payer_cpf,
                token=d["token"],
                payment_method_id=d["payment_method_id"],
                installments=d["installments"],
                device_id=d["device_id"],
            )
        except MercadoPagoAPIError:
            raise
        except Exception as exc:
            logger.error("Erro inesperado ao processar pagamento order=%s: %s", order.id, exc)
            return Response(
                {"detail": "Erro ao comunicar com o gateway de pagamento."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        pagamento_kwargs: dict = {
            "order": order,
            "id_pagamento_externo": result["payment_id"],
            "metodo_pagamento": d["metodo"],
            "valor_total": order.total,
            "status": _MP_STATUS_MAP.get(result.get("status", ""), Pagamento.STATUS_PENDING),
            "status_detalhe": result.get("status_detail", ""),
        }

        if d["metodo"] == "pix":
            pagamento_kwargs.update(
                {
                    "qr_code_payload": result["qr_code"],
                    "qr_code_image_b64": result["qr_code_base64"],
                    "ticket_url": result.get("ticket_url", ""),
                    "expiracao_segundos": result["expiracao_segundos"],
                }
            )
        else:
            pagamento_kwargs["parcelas"] = d["installments"]
            if pagamento_kwargs["status"] == Pagamento.STATUS_APPROVED:
                pagamento_kwargs["pago_em"] = timezone.now()
                Order.objects.filter(pk=order.id).update(status="processing")

        pagamento = Pagamento.objects.create(**pagamento_kwargs)
        return Response(PagamentoSerializer(pagamento).data, status=status.HTTP_201_CREATED)


class PagamentoStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: object, pk: int) -> Response:
        try:
            pagamento = Pagamento.objects.select_related("order").get(
                pk=pk, order__user=request.user
            )
        except Pagamento.DoesNotExist:
            return Response({"detail": "Pagamento não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if pagamento.status not in _MP_FINAL_STATUSES:
            try:
                mp_data = MercadoPagoService.buscar_pagamento(pagamento.id_pagamento_externo)
                _sync_pagamento(pagamento, mp_data)
            except MercadoPagoAPIError as exc:
                logger.warning("Falha ao consultar MP pagamento=%s: %s", pk, exc)

        return Response(PagamentoSerializer(pagamento).data)


class WebhookMercadoPagoView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request: object, *args: object, **kwargs: object) -> Response:
        notif_type: str = request.data.get("type") or request.query_params.get("topic", "")
        data_id: str = (
            request.data.get("data", {}).get("id")
            or request.query_params.get("id", "")
        )

        if notif_type == "payment" and data_id:
            threading.Thread(
                target=_process_webhook,
                args=(str(data_id),),
                daemon=True,
            ).start()

        return Response(status=status.HTTP_200_OK)


def _sync_pagamento(pagamento: Pagamento, mp_data: dict) -> None:
    new_status = _MP_STATUS_MAP.get(mp_data.get("status", ""), pagamento.status)
    pagamento.status = new_status
    pagamento.status_detalhe = mp_data.get("status_detail", "")
    update_fields = ["status", "status_detalhe", "data_atualizacao"]

    if new_status == Pagamento.STATUS_APPROVED and not pagamento.pago_em:
        pagamento.pago_em = timezone.now()
        update_fields.append("pago_em")
        Order.objects.filter(pk=pagamento.order_id, status="pending").update(status="processing")

    pagamento.save(update_fields=update_fields)


def _process_webhook(payment_id: str) -> None:
    try:
        try:
            pagamento = Pagamento.objects.select_related("order").get(
                id_pagamento_externo=payment_id
            )
        except Pagamento.DoesNotExist:
            pagamento = None

        if pagamento and pagamento.status in _MP_FINAL_STATUSES:
            return

        mp_data = MercadoPagoService.buscar_pagamento(payment_id)

        if pagamento is None:
            ext_ref: str = mp_data.get("external_reference", "")
            if not ext_ref.startswith("order_"):
                return
            order_id = int(ext_ref.split("_")[1])
            pagamento = (
                Pagamento.objects.select_related("order")
                .filter(order_id=order_id, status=Pagamento.STATUS_PENDING)
                .latest("data_criacao")
            )

        _sync_pagamento(pagamento, mp_data)
    except Exception as exc:
        logger.error("Webhook MP payment_id=%s falhou: %s", payment_id, exc)
