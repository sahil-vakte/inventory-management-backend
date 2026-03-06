from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .models import UserType
from .serializers import UserTypeSerializer

from django.contrib.auth import get_user_model
from rest_framework import filters
from .serializers import UserSerializer

User = get_user_model()


class UserTypeViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for UserType."""
    queryset = UserType.objects.all()
    serializer_class = UserTypeSerializer
    permission_classes = [IsAdminUser]


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin-only read endpoint for users including their usertype."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['id', 'username', 'email']
