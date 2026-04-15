from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['price', 'stock', 'is_active']
    fieldsets = [
        (None, {'fields': ['name', 'description', 'category', 'image', 'price', 'stock', 'is_active']}),
        ('Dimensões para cálculo de frete', {
            'fields': ['peso', 'comprimento', 'largura', 'altura'],
            'description': 'Peso em kg e dimensões em cm.',
        }),
    ]
