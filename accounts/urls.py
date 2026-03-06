from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import UserTypeViewSet

router = DefaultRouter()
router.register(r'usertypes', UserTypeViewSet, basename='usertype')

urlpatterns = router.urls
