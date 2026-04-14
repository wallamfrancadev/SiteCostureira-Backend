from rest_framework import serializers
from .models import Order, OrderItem
from produtos.models import Product


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_image = serializers.ImageField(source='product.image', read_only=True)

    class Meta:
        model = OrderItem
        fields = ('id', 'product', 'product_name', 'product_image', 'quantity', 'subtotal')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'total', 'status', 'status_display',
            'shipping_address', 'shipping_city', 'shipping_state', 'shipping_cep',
            'items', 'created_at', 'updated_at',
        )
        read_only_fields = ('total', 'status', 'created_at', 'updated_at')


class OrderCreateSerializer(serializers.Serializer):
    items = OrderItemCreateSerializer(many=True, min_length=1)
    shipping_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    shipping_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    shipping_state = serializers.CharField(max_length=2, required=False, allow_blank=True)
    shipping_cep = serializers.CharField(max_length=9, required=False, allow_blank=True)

    def validate_items(self, items):
        product_ids = [i['product_id'] for i in items]
        products = Product.objects.filter(id__in=product_ids, is_active=True)
        found_ids = set(products.values_list('id', flat=True))

        missing = set(product_ids) - found_ids
        if missing:
            raise serializers.ValidationError(f"Produtos não encontrados ou inativos: {missing}")

        # Verificar estoque
        product_map = {p.id: p for p in products}
        for item in items:
            product = product_map[item['product_id']]
            if product.stock < item['quantity']:
                raise serializers.ValidationError(
                    f"Estoque insuficiente para '{product.name}'. Disponível: {product.stock}."
                )

        return items

    def create(self, validated_data):
        user = self.context['request'].user
        items_data = validated_data.pop('items')

        product_ids = [i['product_id'] for i in items_data]
        product_map = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

        total = sum(
            product_map[i['product_id']].price * i['quantity']
            for i in items_data
        )

        order = Order.objects.create(user=user, total=total, **validated_data)

        for item in items_data:
            product = product_map[item['product_id']]
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item['quantity'],
                subtotal=product.price * item['quantity'],
            )
            # Decrementar estoque
            product.stock -= item['quantity']
            product.save(update_fields=['stock'])

        return order
