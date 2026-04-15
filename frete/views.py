from __future__ import annotations

import logging
from decimal import Decimal

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from produtos.models import Product
from .serializers import FreteInputSerializer, FreteOpcaoSerializer
from .services import calcular_frete

logger = logging.getLogger(__name__)


class CalcularFreteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        serializer = FreteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        product_ids = [i['product_id'] for i in d['items']]
        products = {p.id: p for p in Product.objects.filter(id__in=product_ids, is_active=True)}

        missing = set(product_ids) - set(products)
        if missing:
            return Response({'detail': f'Produtos não encontrados: {missing}'}, status=status.HTTP_400_BAD_REQUEST)

        product_quantities = [(products[i['product_id']], i['quantity']) for i in d['items']]
        valor_total = Decimal(str(sum(float(p.price) * q for p, q in product_quantities)))

        try:
            opcoes = calcular_frete(d['cep_destino'], product_quantities, valor_total)
        except Exception as exc:
            logger.error('Erro ao calcular frete: %s', exc)
            return Response({'detail': 'Não foi possível calcular o frete. Verifique o CEP e tente novamente.'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(FreteOpcaoSerializer(opcoes, many=True).data)
