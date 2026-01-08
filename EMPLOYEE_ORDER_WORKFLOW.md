# Employee Order Workflow Documentation

## Overview

The order management system now supports **manual employee assignment** and **manual stock management**. Automatic stock reservation and fulfillment have been removed in favor of a more controlled, employee-driven workflow.

---

## Key Changes

### 1. **Removed Automatic Stock Operations**
- ❌ No automatic stock reservation when orders are created
- ❌ No automatic stock release when orders are cancelled or deleted
- ✅ Employees manually manage stock through dedicated actions

### 2. **Employee Assignment**
- Each order can be assigned to a specific employee
- Assigned employees are responsible for:
  - Managing stock for the order
  - Processing the order
  - Updating order status
  - Handling fulfillment

### 3. **Removed Fields from OrderItem**
- `stock_reserved` - Removed
- `stock_fulfilled` - Removed

---

## API Endpoints

### Assign Employee to Order
**POST** `/api/v1/orders/{id}/assign-employee/`

Assign an employee to handle an order.

**Request Body:**
```json
{
  "employee_id": 2
}
```

**Response:**
```json
{
  "message": "Order assigned to john_doe",
  "order": { ... }
}
```

---

### Unassign Employee from Order
**POST** `/api/v1/orders/{id}/unassign-employee/`

Remove employee assignment from an order.

**Response:**
```json
{
  "message": "Employee unassigned from order",
  "order": { ... }
}
```

---

### Get My Assigned Orders
**GET** `/api/v1/orders/my-assigned-orders/`

Retrieve all orders assigned to the currently logged-in employee.

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "order_number": "ORD-20260108-0001",
      "customer_name": "John Smith",
      "assigned_to": 2,
      "assigned_to_username": "john_doe",
      ...
    }
  ]
}
```

---

### Filter Orders by Assigned Employee
**GET** `/api/v1/orders/?assigned_to={employee_id}`

Filter orders by assigned employee.

**Example:**
```
GET /api/v1/orders/?assigned_to=2
```

---

## Stock Management Workflow

Since automatic stock operations are disabled, employees must manually manage stock through the stock API:

### Reserve Stock for Order
**POST** `/api/v1/stock/{sku}/reserve/`

```json
{
  "quantity": 10,
  "reason": "Reserved for Order ORD-20260108-0001"
}
```

### Release Stock
**POST** `/api/v1/stock/{sku}/release/`

```json
{
  "quantity": 10,
  "reason": "Released from cancelled Order ORD-20260108-0001"
}
```

### Adjust Stock
**POST** `/api/v1/stock/{sku}/adjust/`

```json
{
  "quantity": -10,
  "reason": "Fulfilled Order ORD-20260108-0001"
}
```

---

## Typical Order Workflow

### 1. **Order Created**
- Admin or system creates an order
- No stock is reserved automatically

### 2. **Admin Assigns Employee**
```bash
POST /api/v1/orders/109/assign-employee/
{
  "employee_id": 2
}
```

### 3. **Employee Reviews Assigned Orders**
```bash
GET /api/v1/orders/my-assigned-orders/
```

### 4. **Employee Reserves Stock**
For each item in the order:
```bash
POST /api/v1/stock/109LT-BLK/reserve/
{
  "quantity": 5,
  "reason": "Reserved for Order ORD-20260108-0001"
}
```

### 5. **Employee Processes Order**
```bash
POST /api/v1/orders/109/start-processing/
```

### 6. **Employee Ships Order**
```bash
POST /api/v1/orders/109/ship/
{
  "tracking_number": "1Z999AA10123456784",
  "carrier": "UPS"
}
```

### 7. **Employee Adjusts Stock (Fulfillment)**
For each shipped item:
```bash
POST /api/v1/stock/109LT-BLK/adjust/
{
  "quantity": -5,
  "reason": "Shipped Order ORD-20260108-0001"
}
```

---

## Admin Interface

### Order Admin
- View **assigned_to** in order list
- Filter orders by **assigned_to**
- Assign employees directly in the order detail page

### Employee Management
Use Django's built-in User admin to:
- Create employee accounts
- Assign permissions
- Manage employee groups

---

## User Roles

### Admin
- Create and manage orders
- Assign employees to orders
- View all orders
- Override stock operations

### Employee
- View assigned orders via `/api/v1/orders/my-assigned-orders/`
- Manage stock for assigned orders
- Update order status
- Ship orders

---

## Migration Notes

The following migration has been applied:
- **0002_remove_orderitem_stock_fulfilled_and_more.py**
  - Removed `stock_fulfilled` field from OrderItem
  - Removed `stock_reserved` field from OrderItem
  - Added `assigned_to` field to Order

---

## Benefits of Manual Stock Management

1. **Better Control**: Employees have full visibility and control over stock operations
2. **Audit Trail**: All stock movements are tracked with reasons
3. **Flexibility**: Handle edge cases and special situations manually
4. **Accountability**: Clear assignment of responsibility to specific employees
5. **Error Prevention**: Reduces automatic errors from system-triggered stock operations

---

## Example API Calls

### Complete Example: Order Assignment and Processing

```bash
# 1. Admin assigns order to employee
curl -X POST http://localhost:8000/api/v1/orders/109/assign-employee/ \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"employee_id": 2}'

# 2. Employee gets their assigned orders
curl -X GET http://localhost:8000/api/v1/orders/my-assigned-orders/ \
  -H "Authorization: Bearer {employee_token}"

# 3. Employee reserves stock for order items
curl -X POST http://localhost:8000/api/v1/stock/109LT-BLK/reserve/ \
  -H "Authorization: Bearer {employee_token}" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 5, "reason": "Order ORD-20260108-0001"}'

# 4. Employee processes the order
curl -X POST http://localhost:8000/api/v1/orders/109/start-processing/ \
  -H "Authorization: Bearer {employee_token}"

# 5. Employee ships the order
curl -X POST http://localhost:8000/api/v1/orders/109/ship/ \
  -H "Authorization: Bearer {employee_token}" \
  -H "Content-Type: application/json" \
  -d '{"tracking_number": "1Z999AA10123456784", "carrier": "UPS"}'

# 6. Employee adjusts stock after shipping
curl -X POST http://localhost:8000/api/v1/stock/109LT-BLK/adjust/ \
  -H "Authorization: Bearer {employee_token}" \
  -H "Content-Type: application/json" \
  -d '{"quantity": -5, "reason": "Shipped Order ORD-20260108-0001"}'
```

---

## Summary

The new workflow puts employees in control of order fulfillment and stock management, providing better accountability, flexibility, and control over the entire order lifecycle.
