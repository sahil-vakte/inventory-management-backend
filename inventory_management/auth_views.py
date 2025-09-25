from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


class CustomAuthToken(ObtainAuthToken):
    """
    Custom token authentication endpoint that returns user info along with token
    """
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                          context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'user_id': user.pk,
                'username': user.username,
                'email': user.email,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'created': created
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def token_info(request):
    """
    Get information about the current authentication token
    """
    if request.user.is_authenticated:
        try:
            token = Token.objects.get(user=request.user)
            return Response({
                'user_id': request.user.pk,
                'username': request.user.username,
                'email': request.user.email,
                'is_staff': request.user.is_staff,
                'is_superuser': request.user.is_superuser,
                'token_key': token.key[:8] + '...'  # Show only first 8 characters for security
            })
        except Token.DoesNotExist:
            return Response({
                'error': 'No token found for user'
            }, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({
            'error': 'Authentication required'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['DELETE'])
def logout_token(request):
    """
    Delete the user's authentication token (logout)
    """
    if request.user.is_authenticated:
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
            return Response({
                'message': 'Token deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
        except Token.DoesNotExist:
            return Response({
                'error': 'No token found for user'
            }, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({
            'error': 'Authentication required'
        }, status=status.HTTP_401_UNAUTHORIZED)