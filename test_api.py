#!/usr/bin/env python
"""
Test script for Django Inventory Management API Token Authentication
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_token_auth():
    print("=== Testing Token Authentication API ===\n")
    
    # Test 1: Get authentication token
    print("1. Testing token authentication...")
    auth_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/token/",
            json=auth_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Token authentication successful!")
            print(f"Token: {token_data['token'][:8]}...")
            print(f"Username: {token_data['username']}")
            print(f"Email: {token_data['email']}")
            print(f"Is Staff: {token_data['is_staff']}")
            
            token = token_data['token']
            
            # Test 2: Use token to access API
            print("\n2. Testing API access with token...")
            headers = {"Authorization": f"Token {token}"}
            
            api_response = requests.get(f"{BASE_URL}/api/v1/", headers=headers)
            print(f"API Root Status: {api_response.status_code}")
            
            if api_response.status_code == 200:
                print("✅ API access with token successful!")
                api_data = api_response.json()
                print(f"API Message: {api_data['message']}")
                print(f"Version: {api_data['version']}")
            else:
                print("❌ API access failed")
                print(f"Error: {api_response.text}")
            
            # Test 3: Token info endpoint
            print("\n3. Testing token info endpoint...")
            info_response = requests.get(
                f"{BASE_URL}/api/v1/auth/token/info/",
                headers=headers
            )
            print(f"Token Info Status: {info_response.status_code}")
            
            if info_response.status_code == 200:
                print("✅ Token info successful!")
                info_data = info_response.json()
                print(f"User ID: {info_data['user_id']}")
                print(f"Username: {info_data['username']}")
            else:
                print("❌ Token info failed")
                
        else:
            print("❌ Token authentication failed!")
            print(f"Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure Django server is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_colors_api():
    print("\n=== Testing Colors API with Token ===\n")
    
    # First get token
    auth_data = {"username": "admin", "password": "admin123"}
    auth_response = requests.post(f"{BASE_URL}/api/v1/auth/token/", json=auth_data)
    
    if auth_response.status_code == 200:
        token = auth_response.json()['token']
        headers = {"Authorization": f"Token {token}"}
        
        # Test colors endpoint
        colors_response = requests.get(f"{BASE_URL}/api/v1/colors/", headers=headers)
        print(f"Colors API Status: {colors_response.status_code}")
        
        if colors_response.status_code == 200:
            print("✅ Colors API access successful!")
            colors_data = colors_response.json()
            print(f"Total colors: {colors_data.get('count', 'Unknown')}")
        else:
            print("❌ Colors API access failed")
            print(f"Error: {colors_response.text}")
    else:
        print("❌ Failed to get token for colors test")

if __name__ == "__main__":
    test_token_auth()
    test_colors_api()