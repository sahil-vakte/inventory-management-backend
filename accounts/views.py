from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from .models import UserType
from .serializers import UserTypeSerializer


class UserTypeViewSet(viewsets.ModelViewSet):
    """Admin-only CRUD for UserType."""
    queryset = UserType.objects.all()
    serializer_class = UserTypeSerializer
    permission_classes = [IsAdminUser]
