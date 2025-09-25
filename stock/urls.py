from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockItemViewSet, StockMovementViewSet

router = DefaultRouter()
router.register(r'stock', StockItemViewSet)
router.register(r'movements', StockMovementViewSet)

urlpatterns = [
    path('', include(router.urls)),
]