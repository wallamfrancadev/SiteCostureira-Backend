from django.contrib import admin

from .models import Pagamento


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "metodo_pagamento", "valor_total", "status", "parcelas", "data_criacao"]
    list_filter = ["status", "metodo_pagamento", "data_criacao"]
    search_fields = ["id_pagamento_externo", "order__id"]
    readonly_fields = [
        "id_pagamento_externo",
        "metodo_pagamento",
        "valor_total",
        "status",
        "status_detalhe",
        "qr_code_payload",
        "ticket_url",
        "expiracao_segundos",
        "parcelas",
        "data_criacao",
        "data_atualizacao",
        "pago_em",
        "order",
    ]
    ordering = ["-data_criacao"]
