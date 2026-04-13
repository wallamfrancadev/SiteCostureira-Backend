from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import SiteInfo, Banner
from .serializers import SiteInfoSerializer, BannerSerializer


class SiteInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para informações do site"""
    queryset = SiteInfo.objects.all()
    serializer_class = SiteInfoSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para banners"""
    queryset = Banner.objects.filter(is_active=True)
    serializer_class = BannerSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
