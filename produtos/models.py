from django.db import models


class Category(models.Model):
    """Modelo para categorias de produtos"""
    name = models.CharField(max_length=100, verbose_name="Nome")
    description = models.TextField(blank=True, verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """Modelo para produtos"""
    name = models.CharField(max_length=200, verbose_name="Nome")
    description = models.TextField(verbose_name="Descrição")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço")
    stock = models.IntegerField(default=0, verbose_name="Estoque")
    image = models.ImageField(upload_to='produtos/', blank=True, null=True, verbose_name="Imagem")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products', verbose_name="Categoria")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    peso = models.DecimalField(max_digits=6, decimal_places=3, default=0.3, verbose_name="Peso (kg)")
    comprimento = models.DecimalField(max_digits=6, decimal_places=1, default=20.0, verbose_name="Comprimento (cm)")
    largura = models.DecimalField(max_digits=6, decimal_places=1, default=15.0, verbose_name="Largura (cm)")
    altura = models.DecimalField(max_digits=6, decimal_places=1, default=5.0, verbose_name="Altura (cm)")

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['-created_at']

    def __str__(self):
        return self.name
