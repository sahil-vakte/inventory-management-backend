from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that returns additional user information
    """
    
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['username'] = user.username
        token['email'] = user.email
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        
        # Add extra responses here
        data.update({
            'user_id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'is_staff': self.user.is_staff,
            'is_superuser': self.user.is_superuser,
        })
        
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view with additional user info
    """
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def jwt_user_info(request):
    """
    Get information about the current authenticated user from JWT
    """
    return Response({
        'user_id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
        'auth_method': 'JWT',
        'message': 'User authenticated with JWT token'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def jwt_logout(request):
    """
    Logout by blacklisting the refresh token
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required for logout'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'message': 'Successfully logged out'},
            status=status.HTTP_205_RESET_CONTENT
        )
    except Exception as e:
        return Response(
            {'error': f'Error during logout: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def jwt_register(request):
    """
    Register a new user and return JWT tokens.
    Only authenticated admin users (`is_staff` or `is_superuser`) may create users.
    """
    # require admin privileges
    if not (request.user and (request.user.is_staff or request.user.is_superuser)):
        return Response({'error': 'Admin privileges required to register users.'}, status=status.HTTP_403_FORBIDDEN)
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    # accept either first_name/last_name or fname/lname keys
    first_name = request.data.get('first_name') or request.data.get('fname') or ''
    last_name = request.data.get('last_name') or request.data.get('lname') or ''
    # position is the UserType PK (admins manage user types); accept either 'position' or 'usertype'
    position = request.data.get('position') or request.data.get('usertype')

    if not username or not email:
        return Response(
            {'error': 'Username and email are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # generate a secure random password if not provided
    generated_password = None
    if not password:
        generated_password = get_random_string(12)
        password = generated_password
    
    if User.objects.filter(username=username).exists():
        return Response(
            {'error': 'Username already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if User.objects.filter(email=email).exists():
        return Response(
            {'error': 'Email already exists'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
        )

        # attach UserType via Profile (creates Profile if needed)
        if position:
            try:
                from django.apps import apps
                from django.conf import settings
                UserType = apps.get_model('accounts', 'UserType')
                user_type = UserType.objects.get(pk=position)
                # create or update profile
                Profile = apps.get_model('accounts', 'Profile')
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.usertype = user_type
                # store plaintext password per admin requirement
                profile.plain_password = password
                profile.save()
            except Exception:
                # ignore usertype attachment errors (missing model or bad id)
                pass
        
        resp = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'message': 'User registered successfully'
        }

        # Include usertype info from Profile if available
        try:
            ut = None
            # prefer profile relation
            profile = getattr(user, 'profile', None)
            if profile and getattr(profile, 'usertype', None):
                ut = profile.usertype
            if ut:
                resp['usertype'] = {'id': ut.id, 'name': ut.name}
        except Exception:
            pass

        # include generated password in response when we auto-created one
        if generated_password:
            resp['password'] = generated_password

        return Response(resp, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Error creating user: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )