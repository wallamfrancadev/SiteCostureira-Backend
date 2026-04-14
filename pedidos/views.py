from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Order
from .serializers import OrderSerializer, OrderCreateSerializer


class OrderListCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items__product')

    def get(self, request):
        orders = self.get_queryset()
        serializer = OrderSerializer(orders, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items__product')


class OrderCancelView(APIView):
    """Cancela um pedido pendente e restaura o estoque dos produtos."""
    permission_classes = [permissions.IsAuthenticated]

    CANCELLABLE_STATUSES = ('pending',)

    def patch(self, request, pk):
        try:
            order = Order.objects.prefetch_related('items__product').get(
                pk=pk, user=request.user
            )
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Pedido não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if order.status not in self.CANCELLABLE_STATUSES:
            return Response(
                {'detail': f'Apenas pedidos com status "{", ".join(self.CANCELLABLE_STATUSES)}" podem ser cancelados.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Restaura estoque de cada item
        for item in order.items.all():
            product = item.product
            product.stock += item.quantity
            product.save(update_fields=['stock'])

        order.status = 'cancelled'
        order.save(update_fields=['status'])

        return Response(
            OrderSerializer(order, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )
