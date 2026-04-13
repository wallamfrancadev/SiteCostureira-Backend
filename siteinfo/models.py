from django.db import models


class SiteInfo(models.Model):
    """Informações gerais do site"""
    site_name = models.CharField(max_length=100, default="Dety Costureira & Artesanatos", verbose_name="Nome do Site")
    about = models.TextField(blank=True, verbose_name="Sobre")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    email = models.EmailField(blank=True, verbose_name="E-mail")
    whatsapp = models.CharField(max_length=20, blank=True, verbose_name="WhatsApp")
    address = models.CharField(max_length=255, blank=True, verbose_name="Endereço")
    instagram = models.URLField(blank=True, verbose_name="Instagram")
    facebook = models.URLField(blank=True, verbose_name="Facebook")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Informação do Site"
        verbose_name_plural = "Informações do Site"

    def __str__(self):
        return self.site_name


class Banner(models.Model):
    """Banners da página inicial"""
    title = models.CharField(max_length=200, verbose_name="Título")
    subtitle = models.CharField(max_length=255, blank=True, verbose_name="Subtítulo")
    image = models.ImageField(upload_to='banners/', verbose_name="Imagem")
    link = models.URLField(blank=True, verbose_name="Link")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    order = models.IntegerField(default=0, verbose_name="Ordem")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Banner"
        verbose_name_plural = "Banners"
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
