from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SiteInfoViewSet, BannerViewSet

router = DefaultRouter()
router.register(r'info', SiteInfoViewSet)
router.register(r'banners', BannerViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
