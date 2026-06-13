from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockItemViewSet, StockMovementViewSet, StockBatchViewSet

router = DefaultRouter()
router.register(r'stock', StockItemViewSet)
router.register(r'movements', StockMovementViewSet)
router.register(r'stock-batches', StockBatchViewSet)

urlpatterns = [
    path(
        'stock-batches/mark-labels-generated',
        StockBatchViewSet.as_view({'post': 'bulk_mark_labels_generated'}),
        name='stock-batches-mark-labels-generated',
    ),
    path(
        'stock-batches//mark-labels-generated',
        StockBatchViewSet.as_view({'post': 'bulk_mark_labels_generated'}),
        name='stock-batches-mark-labels-generated-double-slash',
    ),
    path('', include(router.urls)),
]
