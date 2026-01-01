"""
URL configuration for inventory_management project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView
from .api_views import api_root
from .auth_views import (
    CustomTokenObtainPairView, jwt_user_info, jwt_logout, jwt_register
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API root
    path('api/v1/', api_root, name='api-root'),
    
    # API endpoints
    path('api/v1/', include('products.urls')),
    path('api/v1/', include('colors.urls')),
    path('api/v1/', include('stock.urls')),
    path('api/v1/', include('orders.urls')),
    
    # JWT Authentication endpoints
    path('api/v1/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/v1/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    path('api/v1/auth/user/', jwt_user_info, name='jwt_user_info'),
    path('api/v1/auth/logout/', jwt_logout, name='jwt_logout'),
    path('api/v1/auth/register/', jwt_register, name='jwt_register'),
    
    # Session authentication (for admin and browsable API)
    path('api/auth/', include('rest_framework.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
