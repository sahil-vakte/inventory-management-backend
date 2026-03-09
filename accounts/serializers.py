from rest_framework import serializers
from .models import UserType


class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = ['id', 'name', 'description']


from django.contrib.auth import get_user_model


class UserSerializer(serializers.ModelSerializer):
    usertype = serializers.SerializerMethodField()
    password = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'usertype']

    def get_usertype(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and getattr(profile, 'usertype', None):
            ut = profile.usertype
            return {'id': ut.id, 'name': ut.name}
        return None

    def get_password(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and getattr(profile, 'plain_password', None):
            return profile.plain_password
        return None
