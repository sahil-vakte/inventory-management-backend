from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OrderViewSet,
    OrderItemViewSet,
    OrderBatchViewSet,
    OrderStatusHistoryViewSet,
    public_shipping_label,
)

# Create router
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'order-batches', OrderBatchViewSet, basename='orderbatch')
router.register(r'order-history', OrderStatusHistoryViewSet, basename='orderhistory')

urlpatterns = [
    path(
        'orders/items/lable-printed',
        OrderViewSet.as_view({'patch': 'bulk_update_any_items_lable_printed'}),
        name='orders-items-lable-printed',
    ),
    path(
        'orders/<int:order_id>/shipping-label/public/<path:token>/',
        public_shipping_label,
        name='public-shipping-label',
    ),
    path('', include(router.urls)),
]
