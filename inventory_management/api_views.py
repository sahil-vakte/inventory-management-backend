from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.urls import reverse

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
            'get_token': request.build_absolute_uri('/api/v1/auth/token/'),
            'token_info': request.build_absolute_uri('/api/v1/auth/token/info/'),
            'logout': request.build_absolute_uri('/api/v1/auth/token/logout/'),
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