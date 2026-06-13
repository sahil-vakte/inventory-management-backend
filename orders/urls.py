from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, OrderItemViewSet, OrderStatusHistoryViewSet

# Create router
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='orderitem')
router.register(r'order-history', OrderStatusHistoryViewSet, basename='orderhistory')

urlpatterns = [
    path(
        'orders/items/lable-printed',
        OrderViewSet.as_view({'patch': 'bulk_update_any_items_lable_printed'}),
        name='orders-items-lable-printed',
    ),
    path('', include(router.urls)),
]
