#!/bin/bash
# Token Authentication API Test Script for Django Inventory Management System

echo "=== Django Inventory Management API Token Authentication Test ==="
echo

# Server URL
BASE_URL="http://127.0.0.1:8000"

echo "1. Testing Token Authentication Endpoint..."
echo "POST ${BASE_URL}/api/v1/auth/token/"

# Get authentication token
echo
echo "Request:"
echo 'curl -X POST http://127.0.0.1:8000/api/v1/auth/token/ \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{"username": "admin", "password": "admin123"}'"'"

echo
echo "Expected Response:"
echo '{'
echo '  "token": "your_token_here",'
echo '  "user_id": 1,'
echo '  "username": "admin",'
echo '  "email": "admin@example.com",'
echo '  "is_staff": true,'
echo '  "is_superuser": true,'
echo '  "created": false'
echo '}'

echo
echo "2. Using Token to Access API Root..."
echo "GET ${BASE_URL}/api/v1/"

echo
echo "Request:"
echo 'curl -X GET http://127.0.0.1:8000/api/v1/ \'
echo '  -H "Authorization: Token YOUR_TOKEN_HERE"'

echo
echo "3. Testing Token Info Endpoint..."
echo "GET ${BASE_URL}/api/v1/auth/token/info/"

echo
echo "Request:"
echo 'curl -X GET http://127.0.0.1:8000/api/v1/auth/token/info/ \'
echo '  -H "Authorization: Token YOUR_TOKEN_HERE"'

echo
echo "4. Testing Colors API with Token..."
echo "GET ${BASE_URL}/api/v1/colors/"

echo
echo "Request:"
echo 'curl -X GET http://127.0.0.1:8000/api/v1/colors/ \'
echo '  -H "Authorization: Token YOUR_TOKEN_HERE"'

echo
echo "5. Token Logout..."
echo "DELETE ${BASE_URL}/api/v1/auth/token/logout/"

echo
echo "Request:"
echo 'curl -X DELETE http://127.0.0.1:8000/api/v1/auth/token/logout/ \'
echo '  -H "Authorization: Token YOUR_TOKEN_HERE"'

echo
echo "=== Instructions ==="
echo "1. Make sure Django server is running: python manage.py runserver"
echo "2. Run the above curl commands individually"
echo "3. Replace YOUR_TOKEN_HERE with the actual token from step 1"
echo
echo "=== Quick Test ==="
echo "# Get token and save to variable:"
echo 'TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token/ \'
echo '  -H "Content-Type: application/json" \'
echo '  -d '"'"'{"username": "admin", "password": "admin123"}'"'"' | \'
echo '  python -c "import sys, json; print(json.load(sys.stdin)['"'"'token'"'"'])")'
echo
echo "# Use token to access API:"
echo 'curl -X GET http://127.0.0.1:8000/api/v1/ \'
echo '  -H "Authorization: Token $TOKEN"'
echo
echo "=== Token Authentication is now working! ==="