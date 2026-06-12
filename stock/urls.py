from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockItemViewSet, StockMovementViewSet, StockBatchViewSet

router = DefaultRouter()
router.register(r'stock', StockItemViewSet)
router.register(r'movements', StockMovementViewSet)
router.register(r'stock-batches', StockBatchViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
