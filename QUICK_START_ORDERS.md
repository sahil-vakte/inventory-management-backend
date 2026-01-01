# Order Management - Quick Start Guide

## 🚀 Quick Start (5 Minutes)

### 1. Verify Installation
```bash
# Check migrations are applied
python3 manage.py showmigrations orders

# Should show:
# orders
#  [X] 0001_initial
```

### 2. Start the Server
```bash
python3 manage.py runserver
```

### 3. Get Your JWT Token
```bash
# Login (replace with your credentials)
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }'

# Save the "access" token from response
```

### 4. Test Order Creation
```bash
# Create a simple order
curl -X POST http://localhost:8000/api/v1/orders/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test Customer",
    "customer_email": "test@example.com",
    "customer_phone": "+44 7700 900000",
    "items": [
      {
        "sku": "TEST-SKU-001",
        "product_name": "Test Product",
        "quantity": 2,
        "unit_price": "25.00"
      }
    ]
  }'
```

### 5. Test XML Upload
```bash
# Upload the sample XML file
curl -X POST http://localhost:8000/api/v1/orders/upload-xml/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@sample_order.xml"
```

### 6. View Orders
```bash
# List all orders
curl -X GET http://localhost:8000/api/v1/orders/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get specific order
curl -X GET http://localhost:8000/api/v1/orders/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 📋 Common Operations

### Confirm an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/confirm/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Ship an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/ship/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_number": "TRACK123",
    "carrier": "DHL"
  }'
```

### Cancel an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/cancel/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Customer requested cancellation"
  }'
```

### Get Statistics
```bash
curl -X GET http://localhost:8000/api/v1/orders/stats/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🎯 Testing XML Upload

The `sample_order.xml` file contains 3 test orders:

1. **Complete Order** - All fields populated
2. **Multi-Item Order** - Order with multiple products
3. **Minimal Order** - Only required fields

Upload it to test:
```bash
curl -X POST http://localhost:8000/api/v1/orders/upload-xml/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@sample_order.xml"
```

Expected response:
```json
{
  "message": "XML processed successfully",
  "orders_created": 3,
  "orders_failed": 0,
  "orders": [
    {
      "order_number": "ORD-20260102-0001",
      "customer_name": "John Doe",
      "total_amount": "145.99"
    },
    // ... more orders
  ],
  "errors": []
}
```

## 🔍 Filtering & Search

### Filter by Status
```bash
curl -X GET "http://localhost:8000/api/v1/orders/?order_status=PENDING" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Filter by Date Range
```bash
curl -X GET "http://localhost:8000/api/v1/orders/?date_from=2026-01-01&date_to=2026-01-31" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Search Orders
```bash
curl -X GET "http://localhost:8000/api/v1/orders/?search=john" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Filter by Payment Status
```bash
curl -X GET "http://localhost:8000/api/v1/orders/?payment_status=PAID" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 🎨 Django Admin

Access admin at: `http://localhost:8000/admin/`

Features:
- View all orders with status badges
- Inline edit order items
- View status change history
- Bulk actions (confirm, ship, cancel)
- Advanced filtering

## 📊 Integration with Stock

Orders automatically integrate with stock:

1. **Creating Order** → Reserves stock for each item
2. **Cancelling Order** → Releases reserved stock
3. **Removing Item** → Releases stock for that item
4. **Stock Validation** → Checks availability before order creation

## 🔧 Troubleshooting

### Order Creation Fails
- Check stock availability
- Verify SKU exists in stock system
- Ensure customer_name is provided
- Verify at least one item is included

### XML Upload Fails
- Check XML format matches sample
- Ensure required fields are present (CustomerName, Items)
- Verify file encoding is UTF-8
- Check error messages in response

### Stock Not Reserved
- Verify stock_item exists with matching SKU
- Check available stock quantity
- Review internal_notes on order for warnings

## 🎯 Next Steps

1. ✅ Test basic order creation
2. ✅ Test XML upload with sample file
3. ✅ Test order workflows (confirm, ship, deliver)
4. ✅ Explore Django admin interface
5. ✅ Integrate with your frontend/other systems
6. ✅ Customize XML format if needed

## 📚 Full Documentation

See `ORDER_MANAGEMENT_DOCUMENTATION.md` for complete API reference and details.

---

**Need Help?**
- Check Django admin logs
- Review order status history for audit trail
- Verify JWT token is valid
- Check that orders app is in INSTALLED_APPS
