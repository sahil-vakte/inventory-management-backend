#!/bin/bash

echo "=== Testing Token Authentication Fix ==="
echo

# First, get a token
echo "1. Getting authentication token..."
TOKEN_RESPONSE=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}')

echo "Token response: $TOKEN_RESPONSE"

# Extract token using python
TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('token', 'ERROR'))" 2>/dev/null)

if [ "$TOKEN" = "ERROR" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get token"
    exit 1
fi

echo "✅ Token obtained: ${TOKEN:0:8}..."
echo

# Test the problematic import-excel endpoint
echo "2. Testing colors/import-excel endpoint with token..."
IMPORT_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST \
  "http://127.0.0.1:8000/api/v1/colors/import-excel/" \
  -H "Authorization: Token $TOKEN")

HTTP_CODE=$(echo "$IMPORT_RESPONSE" | grep "HTTP_CODE:" | cut -d: -f2)
BODY=$(echo "$IMPORT_RESPONSE" | grep -v "HTTP_CODE:")

echo "HTTP Status: $HTTP_CODE"
echo "Response: $BODY"

if [ "$HTTP_CODE" = "400" ]; then
    if echo "$BODY" | grep -q "No file provided"; then
        echo "✅ SUCCESS! Import endpoint is now accessible"
        echo "   (400 is expected because no file was provided)"
    else
        echo "❌ Got 400 but wrong error message"
    fi
elif [ "$HTTP_CODE" = "403" ]; then
    echo "❌ STILL GETTING 403 FORBIDDEN - Token auth not working"
else
    echo "? Got HTTP $HTTP_CODE - unexpected but not 403"
fi

echo
echo "=== Postman Instructions ==="
echo "Your token: $TOKEN"
echo
echo "In Postman:"
echo "1. Method: POST"
echo "2. URL: http://localhost:8000/api/v1/colors/import-excel/"
echo "3. Headers tab:"
echo "   - Key: Authorization"
echo "   - Value: Token $TOKEN"
echo "4. Body tab:"
echo "   - Select 'form-data'"
echo "   - Key: file (change type to File)"
echo "   - Value: Select your Excel file"
echo
echo "Expected result: Should work now without 403 error!"