from django.urls import path
from .views import CalcularFreteView

urlpatterns = [
    path('frete/calcular/', CalcularFreteView.as_view()),
]
