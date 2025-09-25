# Django Inventory Management System - Postman Collection

This document provides a complete Postman collection with dummy data for all API endpoints. Import this into Postman or use as a reference for API testing.

## Environment Variables
Set up these environment variables in Postman:
- `base_url`: `http://localhost:8000`
- `access_token`: (will be set automatically after login)
- `refresh_token`: (will be set automatically after login)

---

## 1. Authentication Endpoints

### 1.1 Login (Get JWT Tokens)
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/auth/login/`
**Headers:**
```json
{
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "username": "admin",
  "password": "admin123"
}
```
**Expected Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNjk1NjQzMjAwLCJpYXQiOjE2OTU2Mzk2MDAsImp0aSI6IjEyMzQ1Njc4OTAiLCJ1c2VyX2lkIjoxfQ.example_signature",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTY5NjI0NDQwMCwiaWF0IjoxNjk1NjM5NjAwLCJqdGkiOiIwOTg3NjU0MzIxIiwidXNlcl9pZCI6MX0.example_signature",
  "user_id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "is_staff": true,
  "is_superuser": true
}
```
**Postman Tests:**
```javascript
if (pm.response.code === 200) {
    const responseJson = pm.response.json();
    pm.environment.set("access_token", responseJson.access);
    pm.environment.set("refresh_token", responseJson.refresh);
}
```

### 1.2 Refresh Token
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/auth/token/refresh/`
**Headers:**
```json
{
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "refresh": "{{refresh_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.new_access_token.signature"
}
```

### 1.3 Verify Token
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/auth/token/verify/`
**Headers:**
```json
{
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "token": "{{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{}
```

### 1.4 Get User Info
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/auth/user/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "first_name": "Admin",
  "last_name": "User",
  "is_staff": true,
  "is_superuser": true,
  "date_joined": "2024-01-15T10:30:00Z"
}
```

### 1.5 Register New User
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/auth/register/`
**Headers:**
```json
{
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "newpassword123",
  "first_name": "New",
  "last_name": "User"
}
```
**Expected Response (201 Created):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.access_token.signature",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.refresh_token.signature",
  "user_id": 2,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_staff": false,
  "is_superuser": false
}
```

### 1.6 Logout
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/auth/logout/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "refresh_token": "{{refresh_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

---

## 2. Colors API

### 2.1 List Colors
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/colors/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Query Parameters (Optional):**
- `active_only=true`
- `search=black`
**Expected Response (200 OK):**
```json
{
  "count": 25,
  "next": "http://localhost:8000/api/v1/colors/?page=2",
  "previous": null,
  "results": [
    {
      "color_code": "BK",
      "color_name": "Black",
      "secondary_code": "BLK",
      "hex_code": "#000000",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "is_deleted": false
    },
    {
      "color_code": "WHT",
      "color_name": "White",
      "secondary_code": "WH",
      "hex_code": "#FFFFFF",
      "created_at": "2024-01-15T10:31:00Z",
      "updated_at": "2024-01-15T10:31:00Z",
      "is_deleted": false
    }
  ]
}
```

### 2.2 Create Color
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/colors/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "color_code": "RD",
  "color_name": "Red",
  "secondary_code": "RED",
  "hex_code": "#FF0000"
}
```
**Expected Response (201 Created):**
```json
{
  "color_code": "RD",
  "color_name": "Red",
  "secondary_code": "RED",
  "hex_code": "#FF0000",
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z",
  "is_deleted": false
}
```

### 2.3 Get Color Details
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/colors/BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "color_code": "BK",
  "color_name": "Black",
  "secondary_code": "BLK",
  "hex_code": "#000000",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "is_deleted": false
}
```

### 2.4 Update Color
**Method:** `PUT`
**URL:** `{{base_url}}/api/v1/colors/BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "color_code": "BK",
  "color_name": "Jet Black",
  "secondary_code": "JBK",
  "hex_code": "#000000"
}
```
**Expected Response (200 OK):**
```json
{
  "color_code": "BK",
  "color_name": "Jet Black",
  "secondary_code": "JBK",
  "hex_code": "#000000",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:15:00Z",
  "is_deleted": false
}
```

### 2.5 Delete Color (Soft Delete)
**Method:** `DELETE`
**URL:** `{{base_url}}/api/v1/colors/BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (204 No Content)**

### 2.6 Import Colors from Excel
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/colors/import-excel/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Body (form-data):**
- Key: `file`
- Value: [Choose Excel file]
**Expected Response (200 OK):**
```json
{
  "message": "Colors imported successfully",
  "imported_count": 15,
  "updated_count": 3,
  "errors": []
}
```

---

## 3. Products API

### 3.1 List Products
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/products/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Query Parameters (Optional):**
- `active_only=true`
- `search=fabric`
- `min_price=10.00`
- `max_price=100.00`
- `featured=true`
**Expected Response (200 OK):**
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/products/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "vs_parent_id": "P001",
      "vs_child_id": "C001",
      "parent_reference": "FAB-001",
      "child": "FAB-001-BK",
      "parent_product_title": "Premium Cotton Fabric",
      "child_product_title": "Premium Cotton Fabric - Black",
      "brand": 1,
      "brand_name": "TextilePlus",
      "rrp_price_inc_vat": "45.99",
      "cost_price_inc_vat": "25.50",
      "child_active": true,
      "parent_active": true,
      "featured": false,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "is_deleted": false
    }
  ]
}
```

### 3.2 Create Product
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/products/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "vs_parent_id": "P002",
  "vs_child_id": "C002",
  "parent_reference": "FAB-002",
  "child": "FAB-002-WHT",
  "parent_product_title": "Luxury Silk Fabric",
  "child_product_title": "Luxury Silk Fabric - White",
  "brand": 1,
  "rrp_price_inc_vat": "89.99",
  "cost_price_inc_vat": "45.00",
  "child_active": true,
  "parent_active": true,
  "featured": true
}
```
**Expected Response (201 Created):**
```json
{
  "id": 2,
  "vs_parent_id": "P002",
  "vs_child_id": "C002",
  "parent_reference": "FAB-002",
  "child": "FAB-002-WHT",
  "parent_product_title": "Luxury Silk Fabric",
  "child_product_title": "Luxury Silk Fabric - White",
  "brand": 1,
  "brand_name": "TextilePlus",
  "rrp_price_inc_vat": "89.99",
  "cost_price_inc_vat": "45.00",
  "child_active": true,
  "parent_active": true,
  "featured": true,
  "created_at": "2024-01-15T11:20:00Z",
  "updated_at": "2024-01-15T11:20:00Z",
  "is_deleted": false
}
```

### 3.3 Get Product Details
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/products/1/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "id": 1,
  "vs_parent_id": "P001",
  "vs_child_id": "C001",
  "parent_reference": "FAB-001",
  "child": "FAB-001-BK",
  "parent_product_title": "Premium Cotton Fabric",
  "child_product_title": "Premium Cotton Fabric - Black",
  "brand": 1,
  "brand_name": "TextilePlus",
  "rrp_price_inc_vat": "45.99",
  "cost_price_inc_vat": "25.50",
  "child_active": true,
  "parent_active": true,
  "featured": false,
  "subtitle": "High-quality cotton fabric",
  "description": "Premium grade cotton fabric suitable for various applications",
  "weight": "200.00",
  "composition": "100% Cotton",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "is_deleted": false
}
```

### 3.4 Update Product
**Method:** `PUT`
**URL:** `{{base_url}}/api/v1/products/1/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "vs_parent_id": "P001",
  "vs_child_id": "C001",
  "parent_reference": "FAB-001",
  "child": "FAB-001-BK",
  "parent_product_title": "Premium Cotton Fabric - Updated",
  "child_product_title": "Premium Cotton Fabric - Black - Updated",
  "brand": 1,
  "rrp_price_inc_vat": "49.99",
  "cost_price_inc_vat": "27.50",
  "child_active": true,
  "parent_active": true,
  "featured": true
}
```

### 3.5 Delete Product (Soft Delete)
**Method:** `DELETE`
**URL:** `{{base_url}}/api/v1/products/1/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (204 No Content)**

### 3.6 Import Products from Excel
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/products/import-excel/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Body (form-data):**
- Key: `file`
- Value: [Choose Excel file]
**Expected Response (200 OK):**
```json
{
  "message": "Products imported successfully",
  "imported_count": 45,
  "updated_count": 12,
  "errors": []
}
```

### 3.7 Get Product Statistics
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/products/stats/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "total_products": 150,
  "active_products": 145,
  "inactive_products": 5,
  "featured_products": 25,
  "avg_rrp_price": "67.45",
  "avg_cost_price": "35.20"
}
```

---

## 4. Stock API

### 4.1 List Stock Items
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Query Parameters (Optional):**
- `stock_status=low_stock`
- `min_stock=5`
- `max_stock=100`
- `product_type=109LT`
- `color__color_code=BK`
**Expected Response (200 OK):**
```json
{
  "count": 85,
  "next": "http://localhost:8000/api/v1/stock/?page=2",
  "previous": null,
  "results": [
    {
      "sku": "109LT_BK",
      "product_type": "109LT",
      "color": "BK",
      "color_name": "Black",
      "available_stock_rolls": 26,
      "reserved_stock": 5,
      "total_stock": 31,
      "stock_status": "in_stock",
      "min_stock_level": 10,
      "reorder_point": 15,
      "location": "A1-B2-C3",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "is_deleted": false
    },
    {
      "sku": "109LT_WHT",
      "product_type": "109LT",
      "color": "WHT",
      "color_name": "White",
      "available_stock_rolls": 13,
      "reserved_stock": 2,
      "total_stock": 15,
      "stock_status": "low_stock",
      "min_stock_level": 10,
      "reorder_point": 15,
      "location": "A1-B2-C4",
      "created_at": "2024-01-15T10:31:00Z",
      "updated_at": "2024-01-15T10:31:00Z",
      "is_deleted": false
    }
  ]
}
```

### 4.2 Create Stock Item
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "sku": "109LT_RD",
  "product_type": "109LT",
  "color": "RD",
  "available_stock_rolls": 20,
  "min_stock_level": 5,
  "reorder_point": 10,
  "location": "A1-B2-C5"
}
```
**Expected Response (201 Created):**
```json
{
  "sku": "109LT_RD",
  "product_type": "109LT",
  "color": "RD",
  "color_name": "Red",
  "available_stock_rolls": 20,
  "reserved_stock": 0,
  "total_stock": 20,
  "stock_status": "in_stock",
  "min_stock_level": 5,
  "reorder_point": 10,
  "location": "A1-B2-C5",
  "created_at": "2024-01-15T11:25:00Z",
  "updated_at": "2024-01-15T11:25:00Z",
  "is_deleted": false
}
```

### 4.3 Get Stock Item Details
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "sku": "109LT_BK",
  "product_type": "109LT",
  "color": "BK",
  "color_name": "Black",
  "available_stock_rolls": 26,
  "reserved_stock": 5,
  "total_stock": 31,
  "stock_status": "in_stock",
  "min_stock_level": 10,
  "reorder_point": 15,
  "location": "A1-B2-C3",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "is_deleted": false
}
```

### 4.4 Update Stock Item
**Method:** `PUT`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "sku": "109LT_BK",
  "product_type": "109LT",
  "color": "BK",
  "available_stock_rolls": 30,
  "min_stock_level": 12,
  "reorder_point": 18,
  "location": "A1-B2-C3"
}
```

### 4.5 Delete Stock Item (Soft Delete)
**Method:** `DELETE`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (204 No Content)**

### 4.6 Adjust Stock Level
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/adjust-stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "quantity": 10,
  "reason": "New stock arrival from supplier"
}
```
**Expected Response (200 OK):**
```json
{
  "message": "Stock adjusted successfully",
  "sku": "109LT_BK",
  "previous_stock": 26,
  "new_stock": 36,
  "adjustment": 10,
  "reason": "New stock arrival from supplier"
}
```

### 4.7 Reserve Stock
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/reserve-stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "quantity": 5,
  "reason": "Order #12345 reservation"
}
```
**Expected Response (200 OK):**
```json
{
  "message": "Stock reserved successfully",
  "sku": "109LT_BK",
  "reserved_quantity": 5,
  "total_reserved": 10,
  "available_stock": 26,
  "reason": "Order #12345 reservation"
}
```

### 4.8 Release Stock
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/stock/109LT_BK/release-stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "quantity": 3,
  "reason": "Order #12345 cancelled"
}
```
**Expected Response (200 OK):**
```json
{
  "message": "Stock released successfully",
  "sku": "109LT_BK",
  "released_quantity": 3,
  "total_reserved": 7,
  "available_stock": 29,
  "reason": "Order #12345 cancelled"
}
```

### 4.9 Import Stock from Excel
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/stock/import-excel/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Body (form-data):**
- Key: `file`
- Value: [Choose Excel file]
**Expected Response (200 OK):**
```json
{
  "message": "Stock imported successfully",
  "imported_count": 65,
  "updated_count": 20,
  "errors": []
}
```

### 4.10 Get Stock Statistics
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/stock/stats/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "total_stock_items": 85,
  "total_stock_rolls": 1245,
  "low_stock_items": 12,
  "out_of_stock_items": 3,
  "reserved_stock_rolls": 156,
  "available_stock_rolls": 1089
}
```

### 4.11 Get Low Stock Items
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/stock/low-stock/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "count": 12,
  "results": [
    {
      "sku": "109LT_WHT",
      "product_type": "109LT",
      "color": "WHT",
      "color_name": "White",
      "available_stock_rolls": 8,
      "min_stock_level": 10,
      "reorder_point": 15,
      "stock_status": "low_stock"
    },
    {
      "sku": "110LT_BK",
      "product_type": "110LT",
      "color": "BK",
      "color_name": "Black",
      "available_stock_rolls": 5,
      "min_stock_level": 8,
      "reorder_point": 12,
      "stock_status": "low_stock"
    }
  ]
}
```

---

## 5. Categories API

### 5.1 List Categories
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/categories/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "count": 15,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "Fabrics",
      "description": "Various types of fabrics",
      "parent": null,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "is_deleted": false
    },
    {
      "id": 2,
      "name": "Cotton",
      "description": "Cotton-based fabrics",
      "parent": 1,
      "created_at": "2024-01-15T10:31:00Z",
      "updated_at": "2024-01-15T10:31:00Z",
      "is_deleted": false
    }
  ]
}
```

### 5.2 Create Category
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/categories/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "name": "Silk",
  "description": "Premium silk fabrics",
  "parent": 1
}
```
**Expected Response (201 Created):**
```json
{
  "id": 3,
  "name": "Silk",
  "description": "Premium silk fabrics",
  "parent": 1,
  "created_at": "2024-01-15T11:30:00Z",
  "updated_at": "2024-01-15T11:30:00Z",
  "is_deleted": false
}
```

---

## 6. Brands API

### 6.1 List Brands
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/brands/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "TextilePlus",
      "description": "Premium textile manufacturer",
      "website": "https://textileplus.com",
      "contact_email": "info@textileplus.com",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "is_deleted": false
    },
    {
      "id": 2,
      "name": "FabricCorp",
      "description": "Industrial fabric solutions",
      "website": "https://fabriccorp.com",
      "contact_email": "contact@fabriccorp.com",
      "created_at": "2024-01-15T10:32:00Z",
      "updated_at": "2024-01-15T10:32:00Z",
      "is_deleted": false
    }
  ]
}
```

### 6.2 Create Brand
**Method:** `POST`
**URL:** `{{base_url}}/api/v1/brands/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}",
  "Content-Type": "application/json"
}
```
**Body (raw JSON):**
```json
{
  "name": "LuxuryTextiles",
  "description": "Luxury fabric brand",
  "website": "https://luxurytextiles.com",
  "contact_email": "hello@luxurytextiles.com"
}
```
**Expected Response (201 Created):**
```json
{
  "id": 3,
  "name": "LuxuryTextiles",
  "description": "Luxury fabric brand",
  "website": "https://luxurytextiles.com",
  "contact_email": "hello@luxurytextiles.com",
  "created_at": "2024-01-15T11:35:00Z",
  "updated_at": "2024-01-15T11:35:00Z",
  "is_deleted": false
}
```

---

## 7. Stock Movements API (Read-Only)

### 7.1 List Stock Movements
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/movements/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Query Parameters (Optional):**
- `stock_item=109LT_BK`
- `movement_type=adjustment`
- `date_from=2024-01-01`
- `date_to=2024-12-31`
**Expected Response (200 OK):**
```json
{
  "count": 156,
  "next": "http://localhost:8000/api/v1/movements/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "stock_item": "109LT_BK",
      "movement_type": "adjustment",
      "quantity": 10,
      "reason": "New stock arrival from supplier",
      "reference": "PO-2024-001",
      "created_by": 1,
      "created_by_username": "admin",
      "created_at": "2024-01-15T11:25:00Z"
    },
    {
      "id": 2,
      "stock_item": "109LT_BK",
      "movement_type": "reservation",
      "quantity": -5,
      "reason": "Order #12345 reservation",
      "reference": "ORD-12345",
      "created_by": 1,
      "created_by_username": "admin",
      "created_at": "2024-01-15T11:30:00Z"
    }
  ]
}
```

### 7.2 Get Movement Details
**Method:** `GET`
**URL:** `{{base_url}}/api/v1/movements/1/`
**Headers:**
```json
{
  "Authorization": "Bearer {{access_token}}"
}
```
**Expected Response (200 OK):**
```json
{
  "id": 1,
  "stock_item": "109LT_BK",
  "stock_item_details": {
    "product_type": "109LT",
    "color": "BK",
    "color_name": "Black"
  },
  "movement_type": "adjustment",
  "quantity": 10,
  "reason": "New stock arrival from supplier",
  "reference": "PO-2024-001",
  "created_by": 1,
  "created_by_username": "admin",
  "created_at": "2024-01-15T11:25:00Z"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid data provided",
  "details": {
    "field_name": ["This field is required."]
  }
}
```

### 401 Unauthorized
```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid",
  "messages": [
    {
      "token_class": "AccessToken",
      "token_type": "access",
      "message": "Token is invalid or expired"
    }
  ]
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "details": "An unexpected error occurred. Please try again later."
}
```

---

## Postman Environment Setup

Create a new environment in Postman with these variables:

| Variable Name | Initial Value | Current Value |
|--------------|---------------|---------------|
| `base_url` | `http://localhost:8000` | `http://localhost:8000` |
| `access_token` | | (will be set after login) |
| `refresh_token` | | (will be set after login) |
| `user_id` | | (will be set after login) |

## Pre-request Script for Authentication

Add this pre-request script to collection or individual requests that need authentication:

```javascript
// Check if access token exists and is not expired
const accessToken = pm.environment.get("access_token");
const refreshToken = pm.environment.get("refresh_token");

if (!accessToken && refreshToken) {
    // Try to refresh token
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/api/v1/auth/token/refresh/",
        method: 'POST',
        header: {
            'Content-Type': 'application/json'
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                refresh: refreshToken
            })
        }
    }, function (err, res) {
        if (err) {
            console.log('Failed to refresh token');
        } else {
            const responseJson = res.json();
            pm.environment.set("access_token", responseJson.access);
        }
    });
}
```

## Collection Tests

Add this test script to automatically handle token refresh:

```javascript
// Check if response indicates expired token
if (pm.response.code === 401) {
    const refreshToken = pm.environment.get("refresh_token");
    if (refreshToken) {
        pm.test("Attempting token refresh", function() {
            pm.sendRequest({
                url: pm.environment.get("base_url") + "/api/v1/auth/token/refresh/",
                method: 'POST',
                header: {
                    'Content-Type': 'application/json'
                },
                body: {
                    mode: 'raw',
                    raw: JSON.stringify({
                        refresh: refreshToken
                    })
                }
            }, function (err, res) {
                if (!err && res.code === 200) {
                    const responseJson = res.json();
                    pm.environment.set("access_token", responseJson.access);
                    // Retry the original request
                    pm.execution.setNextRequest(pm.info.requestName);
                }
            });
        });
    }
}

// Standard success tests
if (pm.response.code >= 200 && pm.response.code < 300) {
    pm.test("Status code is successful", function () {
        pm.response.to.be.success;
    });
    
    pm.test("Response time is less than 2000ms", function () {
        pm.expect(pm.response.responseTime).to.be.below(2000);
    });
}
```

This comprehensive Postman collection document provides all the endpoints, sample data, and automation scripts needed to test your Django Inventory Management System APIs effectively.