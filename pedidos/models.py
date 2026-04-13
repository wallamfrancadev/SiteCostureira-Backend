from django.db import models
from django.contrib.auth.models import User
from produtos.models import Product


class Order(models.Model):
    """Modelo para pedidos"""
    STATUS_CHOICES = [
        ('pending', 'Pendente'),
        ('processing', 'Processando'),
        ('shipped', 'Enviado'),
        ('delivered', 'Entregue'),
        ('cancelled', 'Cancelado'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Usuário")
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Informações de entrega
    shipping_address = models.CharField(max_length=255, blank=True, verbose_name="Endereço de Entrega")
    shipping_city = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    shipping_state = models.CharField(max_length=2, blank=True, verbose_name="Estado")
    shipping_cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-created_at']

    def __str__(self):
        return f"Pedido #{self.id} - {self.user.username}"


class OrderItem(models.Model):
    """Modelo para itens do pedido"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Pedido")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produto")
    quantity = models.IntegerField(default=1, verbose_name="Quantidade")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal")

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
