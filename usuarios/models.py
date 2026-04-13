from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Perfil estendido do usuário"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    address = models.CharField(max_length=255, blank=True, verbose_name="Endereço")
    city = models.CharField(max_length=100, blank=True, verbose_name="Cidade")
    state = models.CharField(max_length=2, blank=True, verbose_name="Estado")
    cep = models.CharField(max_length=9, blank=True, verbose_name="CEP")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Perfil de Usuário"
        verbose_name_plural = "Perfis de Usuários"

    def __str__(self):
        return f"Perfil de {self.user.username}"
