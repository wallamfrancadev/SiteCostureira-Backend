from __future__ import annotations

from rest_framework import serializers

from .models import Pagamento


class PagamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pagamento
        fields = [
            "id",
            "id_pagamento_externo",
            "status",
            "status_detalhe",
            "metodo_pagamento",
            "valor_total",
            "qr_code_payload",
            "qr_code_image_b64",
            "ticket_url",
            "expiracao_segundos",
            "parcelas",
            "data_criacao",
            "pago_em",
            "order",
        ]
        read_only_fields = fields


class CreatePagamentoSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    metodo = serializers.ChoiceField(choices=["pix", "credit_card"])
    payer_email = serializers.EmailField()
    payer_first_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    payer_last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    payer_cpf = serializers.CharField(max_length=14)
    token = serializers.CharField(required=False, allow_blank=True, default="")
    payment_method_id = serializers.CharField(required=False, allow_blank=True, default="")
    installments = serializers.IntegerField(required=False, default=1, min_value=1, max_value=12)
    device_id = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data: dict) -> dict:
        if data["metodo"] == "credit_card":
            if not data.get("token"):
                raise serializers.ValidationError({"token": "Obrigatório para cartão de crédito."})
            if not data.get("payment_method_id"):
                raise serializers.ValidationError({"payment_method_id": "Obrigatório para cartão de crédito."})
        return data
