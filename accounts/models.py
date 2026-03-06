from django.db import models
from django.conf import settings


class UserType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "User Type"
        verbose_name_plural = "User Types"

    def __str__(self):
        return self.name


class Profile(models.Model):
    """User profile linking to a UserType."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    usertype = models.ForeignKey(UserType, null=True, blank=True, on_delete=models.SET_NULL, related_name='profiles')

    def __str__(self):
        return f"Profile for {self.user.username}"
