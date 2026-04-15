from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class MercadoPagoAPIError(Exception):
    def __init__(self, http_status: int, response_body: dict) -> None:
        self.http_status = http_status
        self.response_body = response_body
        super().__init__(str(response_body))


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    if isinstance(exc, MercadoPagoAPIError):
        cause = exc.response_body.get("cause", [{}])
        code = cause[0].get("code", "") if cause else ""
        message = exc.response_body.get("message", "Erro no gateway de pagamento.")

        http_map: dict[int, int] = {
            400: status.HTTP_400_BAD_REQUEST,
            401: status.HTTP_500_INTERNAL_SERVER_ERROR,
            422: status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
        http_code = http_map.get(exc.http_status, status.HTTP_502_BAD_GATEWAY)
        return Response({"detail": message, "code": code}, status=http_code)

    return drf_exception_handler(exc, context)
