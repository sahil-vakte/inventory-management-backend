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
from .api_views import api_root
from .auth_views import CustomAuthToken, token_info, logout_token

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API root
    path('api/v1/', api_root, name='api-root'),
    
    # API endpoints
    path('api/v1/', include('products.urls')),
    path('api/v1/', include('colors.urls')),
    path('api/v1/', include('stock.urls')),
    
    # Authentication
    path('api/auth/', include('rest_framework.urls')),
    path('api/v1/auth/token/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api/v1/auth/token/info/', token_info, name='token_info'),
    path('api/v1/auth/token/logout/', logout_token, name='token_logout'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
