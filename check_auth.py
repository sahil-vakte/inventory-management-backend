#!/usr/bin/env python
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_management.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

def main():
    print("=== Django User and Token Status ===")
    
    # Check users
    users = User.objects.all()
    print(f"Total users: {users.count()}")
    
    if users.exists():
        for user in users:
            print(f"- Username: {user.username}")
            print(f"  Email: {user.email}")
            print(f"  Staff: {user.is_staff}")
            print(f"  Superuser: {user.is_superuser}")
            
            # Check token
            try:
                token = Token.objects.get(user=user)
                print(f"  Token: {token.key[:8]}...")
            except Token.DoesNotExist:
                print("  Token: Not created")
                # Create token for user
                token = Token.objects.create(user=user)
                print(f"  Token created: {token.key[:8]}...")
            print()
    else:
        print("No users found. Creating superuser...")
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        token = Token.objects.create(user=user)
        print(f"Created superuser 'admin' with token: {token.key[:8]}...")

if __name__ == '__main__':
    main()