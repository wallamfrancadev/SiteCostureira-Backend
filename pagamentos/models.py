from __future__ import annotations

from django.db import models

from pedidos.models import Order


class Pagamento(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_IN_PROCESS = "in_process"
    STATUS_IN_MEDIATION = "in_mediation"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendente"),
        (STATUS_APPROVED, "Aprovado"),
        (STATUS_IN_PROCESS, "Em processamento"),
        (STATUS_IN_MEDIATION, "Em mediação"),
        (STATUS_REJECTED, "Recusado"),
        (STATUS_CANCELLED, "Cancelado"),
        (STATUS_REFUNDED, "Estornado"),
    ]

    METODO_PIX = "pix"
    METODO_CARTAO = "credit_card"

    METODO_CHOICES = [
        (METODO_PIX, "PIX"),
        (METODO_CARTAO, "Cartão de crédito"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="pagamentos")
    id_pagamento_externo = models.CharField(
        max_length=50, unique=True, db_column="IdPagamentoExterno"
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING, db_column="Status"
    )
    metodo_pagamento = models.CharField(
        max_length=20, choices=METODO_CHOICES, db_column="MetodoPagamento"
    )
    valor_total = models.DecimalField(
        max_digits=10, decimal_places=2, db_column="ValorTotal"
    )
    qr_code_payload = models.TextField(blank=True, default="")
    qr_code_image_b64 = models.TextField(blank=True, default="")
    ticket_url = models.URLField(max_length=512, blank=True, default="")
    expiracao_segundos = models.IntegerField(default=3600)
    parcelas = models.PositiveSmallIntegerField(default=1)
    status_detalhe = models.CharField(max_length=100, blank=True, default="")
    data_criacao = models.DateTimeField(auto_now_add=True, db_column="DataCriacao")
    data_atualizacao = models.DateTimeField(auto_now=True, db_column="DataAtualizacao")
    pago_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-data_criacao"]
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"

    def __str__(self) -> str:
        return (
            f"{self.get_metodo_pagamento_display()} "
            f"#{self.id_pagamento_externo[:10]} — "
            f"{self.get_status_display()}"
        )
