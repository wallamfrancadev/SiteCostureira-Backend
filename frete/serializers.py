from __future__ import annotations

from rest_framework import serializers


class ItemFreteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class FreteInputSerializer(serializers.Serializer):
    cep_destino = serializers.CharField(min_length=8, max_length=9)
    items = ItemFreteSerializer(many=True, min_length=1)

    def validate_cep_destino(self, value: str) -> str:
        return value.replace('-', '').replace('.', '').strip()


class FreteOpcaoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    transportadora = serializers.CharField()
    servico = serializers.CharField()
    preco = serializers.DecimalField(max_digits=8, decimal_places=2)
    prazo_dias = serializers.IntegerField()
    prazo_com_producao = serializers.IntegerField()
