from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F
from django.urls import reverse

from orders.models import Order
from stock.models import StockItem

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_root(request, format=None):
    """
    API root endpoint providing overview of available endpoints
    """
    return Response({
        'message': 'Welcome to Django Inventory Management System API',
        'version': '1.0.0',
        'authentication': {
            'login': request.build_absolute_uri('/api/v1/auth/login/'),
            'refresh_token': request.build_absolute_uri('/api/v1/auth/token/refresh/'),
            'verify_token': request.build_absolute_uri('/api/v1/auth/token/verify/'),
            'user_info': request.build_absolute_uri('/api/v1/auth/user/'),
            'logout': request.build_absolute_uri('/api/v1/auth/logout/'),
            'register': request.build_absolute_uri('/api/v1/auth/register/'),
            'session_auth': request.build_absolute_uri('/api/auth/'),
        },
        'endpoints': {
            'products': {
                'list': request.build_absolute_uri('/api/v1/products/'),
                'import_excel': request.build_absolute_uri('/api/v1/products/import-excel/'),
                'stats': request.build_absolute_uri('/api/v1/products/stats/'),
            },
            'colors': {
                'list': request.build_absolute_uri('/api/v1/colors/'),
                'import_excel': request.build_absolute_uri('/api/v1/colors/import-excel/'),
                'export_excel': request.build_absolute_uri('/api/v1/colors/export-excel/'),
            },
            'stock': {
                'list': request.build_absolute_uri('/api/v1/stock/'),
                'import_excel': request.build_absolute_uri('/api/v1/stock/import-excel/'),
                'stats': request.build_absolute_uri('/api/v1/stock/stats/'),
                'low_stock': request.build_absolute_uri('/api/v1/stock/low-stock/'),
            },
            'dashboard': {
                'stats': request.build_absolute_uri('/api/v1/dashboard/stats/'),
            },
            'categories': {
                'list': request.build_absolute_uri('/api/v1/categories/'),
            },
            'brands': {
                'list': request.build_absolute_uri('/api/v1/brands/'),
            },
            'movements': {
                'list': request.build_absolute_uri('/api/v1/movements/'),
            }
        },
        'authentication': {
            'session_auth': request.build_absolute_uri('/api/auth/'),
            'token_auth': request.build_absolute_uri('/api/token-auth/'),
        },
        'admin': request.build_absolute_uri('/admin/'),
        'documentation': 'See API_DOCUMENTATION.md for complete API reference'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request, format=None):
    """Combined dashboard counts for orders and stock health."""
    orders = Order.objects.all()
    active_stock = StockItem.objects.filter(is_active=True)

    out_of_stock = active_stock.filter(available_stock_in_mtr=0).count()
    low_stock = active_stock.filter(
        available_stock_in_mtr__gt=0,
        available_stock_in_mtr__lte=F('minimum_stock_level'),
    ).count()
    in_stock = active_stock.filter(
        available_stock_in_mtr__gt=F('minimum_stock_level')
    ).count()

    return Response({
        'orders': {
            'total': orders.count(),
            'new': orders.filter(order_status=Order.STATUS_NEW).count(),
            'label_printed': orders.filter(order_status=Order.STATUS_LABEL_PRINTED).count(),
            'in_progress': orders.filter(order_status=Order.STATUS_IN_PROGRESS).count(),
            'completed': orders.filter(order_status=Order.STATUS_COMPLETED).count(),
            'shipped': orders.filter(order_status=Order.STATUS_SHIPPED).count(),
            'cancelled': orders.filter(order_status=Order.STATUS_CANCELLED).count(),
        },
        'stock': {
            'total_items': StockItem.objects.count(),
            'active_items': active_stock.count(),
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'inactive': StockItem.objects.filter(is_active=False).count(),
        },
    })
