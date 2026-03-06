from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserTypeViewSet, UserViewSet

router = DefaultRouter()
router.register(r'usertypes', UserTypeViewSet, basename='usertype')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = router.urls
