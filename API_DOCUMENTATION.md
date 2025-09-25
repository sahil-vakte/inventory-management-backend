# Django Inventory Management System API Documentation

## Overview
This is a comprehensive Django-based Warehouse Inventory Management System (WIMS) built with Django REST Framework. The system manages products, colors, and stock levels based on the Excel architecture provided.

## System Architecture

### Core Models
1. **Colors** - Manages color codes and names
2. **Products** - Complete product catalog with attributes, pricing, and metadata  
3. **Stock** - Real-time inventory management with movement tracking

### Key Features
- ✅ RESTful API with full CRUD operations
- ✅ Excel import/export functionality
- ✅ Stock level tracking and alerts
- ✅ Product catalog management
- ✅ Color management system
- ✅ Admin interface for data management
- ✅ API authentication and permissions
- ✅ Comprehensive filtering and search
- ✅ Stock movement audit trail

## API Endpoints

### Authentication
- `POST /api/v1/auth/token/` - Get authentication token
- `GET /api/v1/auth/token/info/` - Get current token information
- `DELETE /api/v1/auth/token/logout/` - Logout (delete token)
- `GET/POST /api/auth/` - Django session authentication

### Products API (`/api/v1/products/`)
- `GET /api/v1/products/` - List all products (paginated)
- `POST /api/v1/products/` - Create new product
- `GET /api/v1/products/{id}/` - Get product details
- `PUT /api/v1/products/{id}/` - Update product
- `PATCH /api/v1/products/{id}/` - Partial update product
- `DELETE /api/v1/products/{id}/` - Delete product
- `POST /api/v1/products/import-excel/` - Import products from Excel
- `GET /api/v1/products/stats/` - Get product statistics

#### Query Parameters
- `active_only=true` - Filter only active products
- `min_price=10.00` - Filter by minimum price
- `max_price=100.00` - Filter by maximum price
- `brand={brand_id}` - Filter by brand
- `featured=true` - Filter featured products
- `search=fabric` - Search in title, reference, subtitle

### Colors API (`/api/v1/colors/`)
- `GET /api/v1/colors/` - List all colors
- `POST /api/v1/colors/` - Create new color
- `GET /api/v1/colors/{code}/` - Get color details
- `PUT /api/v1/colors/{code}/` - Update color
- `DELETE /api/v1/colors/{code}/` - Delete color
- `POST /api/v1/colors/import-excel/` - Import colors from Excel
- `GET /api/v1/colors/export-excel/` - Export colors to Excel

### Stock API (`/api/v1/stock/`)
- `GET /api/v1/stock/` - List all stock items
- `POST /api/v1/stock/` - Create new stock item
- `GET /api/v1/stock/{sku}/` - Get stock item details
- `PUT /api/v1/stock/{sku}/` - Update stock item
- `DELETE /api/v1/stock/{sku}/` - Delete stock item
- `POST /api/v1/stock/{sku}/adjust-stock/` - Adjust stock levels
- `POST /api/v1/stock/{sku}/reserve-stock/` - Reserve stock
- `POST /api/v1/stock/{sku}/release-stock/` - Release reserved stock
- `POST /api/v1/stock/import-excel/` - Import stock from Excel
- `GET /api/v1/stock/stats/` - Get stock statistics
- `GET /api/v1/stock/low-stock/` - Get low stock items

#### Query Parameters
- `stock_status=low_stock` - Filter by stock status (low_stock, out_of_stock, in_stock)
- `min_stock=5` - Filter by minimum stock level
- `max_stock=100` - Filter by maximum stock level
- `product_type=109LT` - Filter by product type
- `color__color_code=BK` - Filter by color code

### Categories API (`/api/v1/categories/`)
- `GET /api/v1/categories/` - List all categories
- `POST /api/v1/categories/` - Create new category
- `GET /api/v1/categories/{id}/` - Get category details
- `PUT /api/v1/categories/{id}/` - Update category
- `DELETE /api/v1/categories/{id}/` - Delete category

### Brands API (`/api/v1/brands/`)
- `GET /api/v1/brands/` - List all brands
- `POST /api/v1/brands/` - Create new brand
- `GET /api/v1/brands/{id}/` - Get brand details
- `PUT /api/v1/brands/{id}/` - Update brand
- `DELETE /api/v1/brands/{id}/` - Delete brand

### Stock Movements API (`/api/v1/movements/`)
- `GET /api/v1/movements/` - List all stock movements (read-only)
- `GET /api/v1/movements/{id}/` - Get movement details

## Excel Import Format

### Colors Sheet
```
| ColorCode | ColorName    | Secondary Code |
|-----------|--------------|----------------|
| ABRN      | Auburn Brown | ABRN2          |
| AGD       | Antique Gold | -              |
```

### Product Master Sheet
Required columns: `VS Parent ID`, `VS Child ID`, `Parent Reference`, `Child`, `Parent Product Title`, `Child Product Title`, `Brand`, `RRP Price (Inc VAT)`, `Cost Price (Inc VAT)`, `Child Active`, `Parent Active`

### Current Stock Sheet
```
| ProdTpe | Color Abrvs | SKU      | Available Stock (Rolls) |
|---------|-------------|----------|-------------------------|
| 109LT   | BK          | 109LT BK | 26                      |
| 109LT   | WHT         | 109LT WHT| 13                      |
```

## Authentication
All API endpoints require authentication. You can use:

1. **Token Authentication** - Get token from `/api/v1/auth/token/` and include in headers:
   ```
   Authorization: Token your_token_here
   ```

2. **Session Authentication** - Login via Django admin or `/api/auth/`

### Getting Your Authentication Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'
```

Response:
```json
{
  "token": "your_authentication_token_here",
  "user_id": 1,
  "username": "your_username",
  "email": "user@example.com",
  "is_staff": true,
  "is_superuser": true,
  "created": false
}
```

### Check Token Information
```bash
curl -X GET http://localhost:8000/api/v1/auth/token/info/ \
  -H "Authorization: Token your_token_here"
```

### Logout (Delete Token)
```bash
curl -X DELETE http://localhost:8000/api/v1/auth/token/logout/ \
  -H "Authorization: Token your_token_here"
```

## Example Requests

### Import Colors from Excel
```bash
curl -X POST http://localhost:8000/api/v1/colors/import-excel/ \
  -H "Authorization: Token your_token" \
  -F "file=@colors.xlsx"
```

### Complete Authentication Flow Example
```bash
# Step 1: Get authentication token
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Response:
# {
#   "token": "0457351f123abc...",
#   "user_id": 1,
#   "username": "admin",
#   "email": "admin@example.com", 
#   "is_staff": true,
#   "is_superuser": true,
#   "created": false
# }

# Step 2: Use token for API calls
TOKEN="your_token_from_step_1"
curl -X GET http://localhost:8000/api/v1/colors/ \
  -H "Authorization: Token $TOKEN"

# Step 3: Check token information
curl -X GET http://localhost:8000/api/v1/auth/token/info/ \
  -H "Authorization: Token $TOKEN"
```

### Advanced Token Usage
```bash
# Get token and save to variable (one-liner)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  python -c "import sys, json; print(json.load(sys.stdin)['token'])")

# Use token for multiple API calls
curl -X GET http://localhost:8000/api/v1/ -H "Authorization: Token $TOKEN"
curl -X GET http://localhost:8000/api/v1/colors/ -H "Authorization: Token $TOKEN"
curl -X GET http://localhost:8000/api/v1/products/ -H "Authorization: Token $TOKEN"
curl -X GET http://localhost:8000/api/v1/stock/ -H "Authorization: Token $TOKEN"
```

### Get Low Stock Items
```bash
curl -X GET "http://localhost:8000/api/v1/stock/low-stock/" \
  -H "Authorization: Token your_token"
```

### Adjust Stock Level
```bash
curl -X POST http://localhost:8000/api/v1/stock/109LT_BK/adjust-stock/ \
  -H "Authorization: Token your_token" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 10, "reason": "New stock arrival"}'
```

### Search Products
```bash
curl -X GET "http://localhost:8000/api/v1/products/?search=fabric&active_only=true" \
  -H "Authorization: Token your_token"
```

## Error Handling
All APIs return consistent error responses:
```json
{
  "error": "Error description",
  "details": "Additional details if available"
}
```

## Response Format
Successful responses follow this structure:
- **List endpoints**: Paginated results with `count`, `next`, `previous`, `results`
- **Detail endpoints**: Single object data
- **Create/Update**: Created/updated object data
- **Delete**: 204 No Content

## Development Setup
1. Activate virtual environment: `source .venv/bin/activate`
2. Run migrations: `python manage.py migrate`
3. Create superuser: `python manage.py createsuperuser`
4. Start server: `python manage.py runserver`
5. Access admin: http://localhost:8000/admin/
6. API Root: http://localhost:8000/api/v1/

## Database Schema
- **SQLite** for development (easily replaceable with PostgreSQL/MySQL for production)
- **Optimized indexes** for frequent queries
- **Foreign key relationships** maintained
- **Audit trail** for stock movements