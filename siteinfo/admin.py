from django.contrib import admin
from .models import SiteInfo, Banner


@admin.register(SiteInfo)
class SiteInfoAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'phone', 'email', 'whatsapp']


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_active', 'order', 'created_at']
    list_filter = ['is_active']
    list_editable = ['is_active', 'order']
