#!/usr/bin/env python
"""
Quick test to verify token authentication is working
"""

import requests
import json
import sys
import os

BASE_URL = "http://127.0.0.1:8000"

def test_token_auth():
    print("=== Testing Token Authentication Fix ===")
    print()
    
    # Step 1: Get token
    print("1. Getting authentication token...")
    auth_data = {
        "username": "admin", 
        "password": "admin123"
    }
    
    try:
        # Get token
        token_response = requests.post(
            f"{BASE_URL}/api/v1/auth/token/",
            json=auth_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Token request status: {token_response.status_code}")
        
        if token_response.status_code != 200:
            print(f"❌ Failed to get token: {token_response.text}")
            return False
            
        token_data = token_response.json()
        token = token_data['token']
        print(f"✅ Token obtained: {token[:8]}...")
        print(f"   User: {token_data['username']} ({token_data['email']})")
        
        # Step 2: Test colors API with token
        print()
        print("2. Testing colors API with token...")
        headers = {"Authorization": f"Token {token}"}
        
        colors_response = requests.get(
            f"{BASE_URL}/api/v1/colors/",
            headers=headers,
            timeout=10
        )
        
        print(f"Colors API status: {colors_response.status_code}")
        
        if colors_response.status_code == 200:
            print("✅ Colors API access successful!")
            colors_data = colors_response.json()
            print(f"   Colors count: {colors_data.get('count', 'Unknown')}")
            
            # Step 3: Test import-excel endpoint (the problematic one)
            print()
            print("3. Testing colors import-excel endpoint...")
            
            # Create a dummy file for testing (without actually uploading)
            test_response = requests.post(
                f"{BASE_URL}/api/v1/colors/import-excel/",
                headers=headers,
                timeout=10
            )
            
            print(f"Import-excel status: {test_response.status_code}")
            
            if test_response.status_code == 400:
                # 400 is expected because we didn't send a file
                response_text = test_response.text
                if "No file provided" in response_text:
                    print("✅ Import-excel endpoint accessible! (400 expected - no file)")
                    print("   Authentication is working correctly!")
                    return True
                else:
                    print(f"❌ Unexpected 400 response: {response_text}")
                    return False
            elif test_response.status_code == 403:
                print(f"❌ Still getting 403 Forbidden: {test_response.text}")
                return False
            else:
                print(f"❌ Unexpected status {test_response.status_code}: {test_response.text}")
                return False
                
        else:
            print(f"❌ Colors API failed: {test_response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure Django server is running on port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("Django Inventory Management - Token Authentication Test")
    print("=" * 60)
    
    success = test_token_auth()
    
    print()
    print("=" * 60)
    if success:
        print("🎉 AUTHENTICATION IS WORKING!")
        print()
        print("Postman Instructions:")
        print("1. Set method to POST")
        print("2. URL: http://localhost:8000/api/v1/colors/import-excel/")
        print("3. Headers:")
        print("   - Authorization: Token YOUR_TOKEN_HERE")
        print("   - Content-Type: multipart/form-data (auto-set when adding file)")
        print("4. Body: form-data, key='file', type=File, select your Excel file")
        print()
        print("To get your token:")
        print("POST http://localhost:8000/api/v1/auth/token/")
        print('Body: {"username": "admin", "password": "admin123"}')
    else:
        print("❌ Authentication still has issues. Check Django server logs.")

if __name__ == "__main__":
    main()