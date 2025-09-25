#!/usr/bin/env python
"""
Test script for JWT Authentication in Django Inventory Management API
"""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_jwt_authentication():
    print("=== Testing JWT Authentication ===\n")
    
    # Test 1: Get JWT tokens
    print("1. Testing JWT login...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login/",
            json=login_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Login Status Code: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ JWT login successful!")
            print(f"Access Token: {token_data['access'][:50]}...")
            print(f"Refresh Token: {token_data['refresh'][:50]}...")
            print(f"Username: {token_data['username']}")
            print(f"Email: {token_data['email']}")
            print(f"Is Staff: {token_data['is_staff']}")
            
            access_token = token_data['access']
            refresh_token = token_data['refresh']
            
            # Test 2: Use access token to access API
            print("\n2. Testing API access with JWT...")
            headers = {"Authorization": f"Bearer {access_token}"}
            
            api_response = requests.get(f"{BASE_URL}/api/v1/", headers=headers, timeout=10)
            print(f"API Root Status: {api_response.status_code}")
            
            if api_response.status_code == 200:
                print("✅ API access with JWT successful!")
                api_data = api_response.json()
                print(f"API Message: {api_data['message']}")
                print(f"Version: {api_data['version']}")
            else:
                print("❌ API access failed")
                print(f"Error: {api_response.text}")
                return False
            
            # Test 3: Test user info endpoint
            print("\n3. Testing JWT user info endpoint...")
            user_response = requests.get(
                f"{BASE_URL}/api/v1/auth/user/",
                headers=headers,
                timeout=10
            )
            print(f"User Info Status: {user_response.status_code}")
            
            if user_response.status_code == 200:
                print("✅ JWT user info successful!")
                user_data = user_response.json()
                print(f"User ID: {user_data['user_id']}")
                print(f"Username: {user_data['username']}")
                print(f"Auth Method: {user_data['auth_method']}")
            else:
                print("❌ JWT user info failed")
                print(f"Error: {user_response.text}")
            
            # Test 4: Test token refresh
            print("\n4. Testing JWT token refresh...")
            refresh_response = requests.post(
                f"{BASE_URL}/api/v1/auth/token/refresh/",
                json={"refresh": refresh_token},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            print(f"Refresh Status: {refresh_response.status_code}")
            
            if refresh_response.status_code == 200:
                print("✅ JWT token refresh successful!")
                refresh_data = refresh_response.json()
                print(f"New Access Token: {refresh_data['access'][:50]}...")
                new_access_token = refresh_data['access']
            else:
                print("❌ JWT token refresh failed")
                print(f"Error: {refresh_response.text}")
                new_access_token = access_token
            
            # Test 5: Test colors API with JWT
            print("\n5. Testing colors API with JWT...")
            colors_response = requests.get(
                f"{BASE_URL}/api/v1/colors/",
                headers={"Authorization": f"Bearer {new_access_token}"},
                timeout=10
            )
            print(f"Colors API Status: {colors_response.status_code}")
            
            if colors_response.status_code == 200:
                print("✅ Colors API access successful!")
                colors_data = colors_response.json()
                print(f"Colors count: {colors_data.get('count', 'Unknown')}")
            else:
                print("❌ Colors API access failed")
                print(f"Error: {colors_response.text}")
            
            # Test 6: Test import endpoint (the one that was problematic)
            print("\n6. Testing colors import-excel endpoint with JWT...")
            import_response = requests.post(
                f"{BASE_URL}/api/v1/colors/import-excel/",
                headers={"Authorization": f"Bearer {new_access_token}"},
                timeout=10
            )
            print(f"Import Status: {import_response.status_code}")
            
            if import_response.status_code == 400:
                response_text = import_response.text
                if "No file provided" in response_text:
                    print("✅ Import endpoint accessible! (400 expected - no file)")
                    print("   JWT Authentication is working correctly!")
                    return True, access_token, refresh_token
                else:
                    print(f"❌ Unexpected 400 response: {response_text}")
                    return False, None, None
            elif import_response.status_code == 403:
                print(f"❌ Still getting 403 Forbidden: {import_response.text}")
                return False, None, None
            else:
                print(f"❌ Unexpected status {import_response.status_code}: {import_response.text}")
                return False, None, None
                
        else:
            print("❌ JWT login failed!")
            print(f"Error: {response.text}")
            return False, None, None
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure Django server is running on port 8000")
        return False, None, None
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None, None

def test_jwt_logout(access_token, refresh_token):
    print("\n=== Testing JWT Logout ===")
    
    try:
        logout_response = requests.post(
            f"{BASE_URL}/api/v1/auth/logout/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"refresh_token": refresh_token},
            timeout=10
        )
        
        print(f"Logout Status: {logout_response.status_code}")
        
        if logout_response.status_code == 205:
            print("✅ JWT logout successful!")
            print("Refresh token has been blacklisted")
            return True
        else:
            print(f"❌ Logout failed: {logout_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Logout error: {e}")
        return False

def main():
    print("Django Inventory Management - JWT Authentication Test")
    print("=" * 70)
    
    success, access_token, refresh_token = test_jwt_authentication()
    
    if success and access_token and refresh_token:
        test_jwt_logout(access_token, refresh_token)
    
    print()
    print("=" * 70)
    if success:
        print("🎉 JWT AUTHENTICATION IS WORKING!")
        print()
        print("Postman Instructions for JWT:")
        print("1. Login Endpoint:")
        print("   POST http://localhost:8000/api/v1/auth/login/")
        print("   Body: {\"username\": \"admin\", \"password\": \"admin123\"}")
        print()
        print("2. Use Access Token in Headers:")
        print("   Authorization: Bearer YOUR_ACCESS_TOKEN")
        print()
        print("3. Import Endpoint:")
        print("   POST http://localhost:8000/api/v1/colors/import-excel/")
        print("   Headers: Authorization: Bearer YOUR_ACCESS_TOKEN")
        print("   Body: form-data, key='file', type=File")
        print()
        print("4. Refresh Token when expired:")
        print("   POST http://localhost:8000/api/v1/auth/token/refresh/")
        print("   Body: {\"refresh\": \"YOUR_REFRESH_TOKEN\"}")
        print()
        print("Note: Access tokens expire after 60 minutes")
        print("      Refresh tokens expire after 7 days")
    else:
        print("❌ JWT Authentication has issues. Check Django server logs.")

if __name__ == "__main__":
    main()