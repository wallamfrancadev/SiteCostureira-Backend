from django.urls import path

from .views import CreatePagamentoView, PagamentoStatusView, WebhookMercadoPagoView

urlpatterns = [
    path("pagamentos/", CreatePagamentoView.as_view(), name="pagamento-create"),
    path("pagamentos/<int:pk>/", PagamentoStatusView.as_view(), name="pagamento-status"),
    path("webhook/mercadopago/", WebhookMercadoPagoView.as_view(), name="webhook-mp"),
]
