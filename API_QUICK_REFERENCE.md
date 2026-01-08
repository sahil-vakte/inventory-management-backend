# Quick Reference - Employee Order Management API

## Employee Assignment

### Assign Employee to Order
```http
POST /api/v1/orders/{order_id}/assign-employee/
Authorization: Bearer {token}
Content-Type: application/json

{
  "employee_id": 2
}
```

**Response:**
```json
{
  "message": "Order assigned to john_doe",
  "order": { ... full order details ... }
}
```

---

### Unassign Employee
```http
POST /api/v1/orders/{order_id}/unassign-employee/
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Employee unassigned from order",
  "order": { ... full order details ... }
}
```

---

### Get My Assigned Orders
```http
GET /api/v1/orders/my-assigned-orders/
Authorization: Bearer {token}
```

**Response:**
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 109,
      "order_number": "ORD-20260108-0001",
      "customer_name": "John Smith",
      "assigned_to": 2,
      "assigned_to_username": "john_doe",
      "order_status": "PENDING",
      ...
    }
  ]
}
```

---

### Filter Orders by Employee
```http
GET /api/v1/orders/?assigned_to={employee_id}
Authorization: Bearer {token}
```

---

## Manual Stock Management

### Reserve Stock
```http
POST /api/v1/stock/{sku}/reserve-stock/
Authorization: Bearer {token}
Content-Type: application/json

{
  "quantity": 10
}
```

**Response:**
```json
{
  "message": "Reserved 10 units",
  "reserved_stock": 10,
  "available_stock": 90
}
```

---

### Release Reserved Stock
```http
POST /api/v1/stock/{sku}/release-stock/
Authorization: Bearer {token}
Content-Type: application/json

{
  "quantity": 10
}
```

**Response:**
```json
{
  "message": "Released 10 units",
  "reserved_stock": 0,
  "available_stock": 100
}
```

---

### Adjust Stock (Fulfillment/Receipt)
```http
POST /api/v1/stock/{sku}/adjust-stock/
Authorization: Bearer {token}
Content-Type: application/json

{
  "quantity": -10,
  "reason": "Fulfilled Order ORD-20260108-0001"
}
```

**Response:**
```json
{
  "message": "Stock adjusted by -10",
  "new_stock_level": 90,
  "reason": "Fulfilled Order ORD-20260108-0001"
}
```

---

## Order Processing Workflow

### 1. Get Assigned Orders
```http
GET /api/v1/orders/my-assigned-orders/
```

### 2. Reserve Stock for Each Item
```http
POST /api/v1/stock/109LT-BLK/reserve-stock/
{
  "quantity": 5
}
```

### 3. Start Processing Order
```http
POST /api/v1/orders/109/start-processing/
```

### 4. Ship Order
```http
POST /api/v1/orders/109/ship/
{
  "tracking_number": "1Z999AA10123456784",
  "carrier": "UPS"
}
```

### 5. Adjust Stock (Deduct Shipped Items)
```http
POST /api/v1/stock/109LT-BLK/adjust-stock/
{
  "quantity": -5,
  "reason": "Shipped Order ORD-20260108-0001"
}
```

---

## Order Cancellation Workflow

### 1. Cancel Order
```http
POST /api/v1/orders/109/cancel/
{
  "reason": "Customer requested cancellation"
}
```

### 2. Release Reserved Stock
```http
POST /api/v1/stock/109LT-BLK/release-stock/
{
  "quantity": 5
}
```

---

## Postman Collection Examples

### Environment Variables
```
base_url: http://localhost:8000
token: your_jwt_token_here
employee_id: 2
order_id: 109
sku: 109LT-BLK
```

### Headers
```
Authorization: Bearer {{token}}
Content-Type: application/json
```

---

## Common Errors

### 400 Bad Request
```json
{
  "error": "employee_id is required"
}
```
**Solution:** Include employee_id in request body

---

### 400 Bad Request
```json
{
  "error": "Insufficient stock available"
}
```
**Solution:** Check available stock before reserving

---

### 404 Not Found
```json
{
  "error": "Employee not found"
}
```
**Solution:** Verify employee_id exists in system

---

## Order Fields

### New Fields in Order Response

```json
{
  "assigned_to": 2,
  "assigned_to_username": "john_doe",
  ...
}
```

### Removed Fields from OrderItem

- ❌ `stock_reserved` (removed)
- ❌ `stock_fulfilled` (removed)

---

## Tips

1. **Always include reason** when adjusting stock for audit trail
2. **Use negative quantity** when reducing stock (e.g., -10 for fulfillment)
3. **Use positive quantity** when receiving stock (e.g., +100 for new stock)
4. **Reserve stock** before starting order processing
5. **Release stock** if order is cancelled
6. **Adjust stock** after order is shipped (deduct from available)

---

## Stock States

- **Available Stock**: Total stock in warehouse
- **Reserved Stock**: Stock held for orders (not available for new orders)
- **Total Available**: Available Stock - Reserved Stock

**Example:**
- Available Stock: 100 rolls
- Reserved Stock: 10 rolls
- Total Available: 90 rolls (available for new orders)
