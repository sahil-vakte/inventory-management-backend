# Postman Collection Update Summary

## File Updated
`POSTMAN_COLLECTION_ORDERS.json`

---

## Changes Made

### 1. **Updated Collection Description**
- Added note about manual stock management
- Clarified that automatic stock reservation/release has been removed

### 2. **New Folder: Employee Assignment**
Contains 4 new endpoints for employee order management:

#### A. Assign Employee to Order
- **Method:** POST
- **URL:** `/api/v1/orders/{id}/assign-employee/`
- **Body:**
  ```json
  {
    "employee_id": 2
  }
  ```

#### B. Unassign Employee from Order
- **Method:** POST
- **URL:** `/api/v1/orders/{id}/unassign-employee/`
- **Body:** `{}`

#### C. Get My Assigned Orders
- **Method:** GET
- **URL:** `/api/v1/orders/my-assigned-orders/`
- Returns all orders assigned to the currently logged-in employee

#### D. Filter Orders by Assigned Employee
- **Method:** GET
- **URL:** `/api/v1/orders/?assigned_to=2`
- Filter orders by employee ID

### 3. **New Folder: Manual Stock Management**
Contains 3 endpoints for manual stock operations:

#### A. Reserve Stock for Order
- **Method:** POST
- **URL:** `/api/v1/stock/{sku}/reserve-stock/`
- **Body:**
  ```json
  {
    "quantity": 10
  }
  ```

#### B. Release Reserved Stock
- **Method:** POST
- **URL:** `/api/v1/stock/{sku}/release-stock/`
- **Body:**
  ```json
  {
    "quantity": 10
  }
  ```

#### C. Adjust Stock (Fulfillment)
- **Method:** POST
- **URL:** `/api/v1/stock/{sku}/adjust-stock/`
- **Body:**
  ```json
  {
    "quantity": -10,
    "reason": "Fulfilled Order ORD-20260108-0001"
  }
  ```

### 4. **Updated Existing Endpoints**

#### Create Order (Simple)
- Added `assigned_to` field to request body
  ```json
  {
    "customer_name": "John Doe",
    "assigned_to": 2,
    ...
  }
  ```

#### Create Order (Complete)
- Added `assigned_to` field to request body

#### Cancel Order
- Updated description to clarify that stock must be manually released

### 5. **New Collection Variable**
- Added `employee_id` variable (default: "2")

---

## Collection Structure

The updated collection now has the following structure:

```
Inventory Management - Orders API
├── Authentication
│   ├── Login (Get JWT Token)
│   ├── Refresh Token
│   └── Get Current User Info
├── Orders - CRUD
│   ├── List All Orders
│   ├── Get Order by ID
│   ├── Create Order (Simple)
│   ├── Create Order (Complete)
│   ├── Update Order
│   ├── Partial Update Order
│   ├── Delete Order (Soft Delete)
│   ├── Delete Order (Permanent)
│   └── Restore Deleted Order
├── Order Workflows
│   ├── Confirm Order
│   ├── Start Processing Order
│   ├── Ship Order
│   ├── Mark as Delivered
│   └── Cancel Order
├── Employee Assignment ⭐ NEW
│   ├── Assign Employee to Order
│   ├── Unassign Employee from Order
│   ├── Get My Assigned Orders
│   └── Filter Orders by Assigned Employee
├── Manual Stock Management ⭐ NEW
│   ├── Reserve Stock for Order
│   ├── Release Reserved Stock
│   └── Adjust Stock (Fulfillment)
├── Order Items
│   ├── Add Item to Order
│   ├── Remove Item from Order
│   ├── List All Order Items
│   └── Get Order Item by ID
├── XML Upload
│   └── Upload XML File
├── Filtering & Search
│   ├── Filter by Status (Pending)
│   ├── Filter by Payment Status (Paid)
│   ├── Filter by Date Range
│   ├── Filter by Total Amount Range
│   ├── Filter by Order Source (XML)
│   ├── Search Orders
│   ├── Include Deleted Orders
│   ├── Only Deleted Orders
│   └── Combined Filters
├── Statistics & Reporting
│   ├── Get Order Statistics
│   ├── Order Status History
│   └── Filter History by Order
└── Other Resources
    ├── List Products
    ├── List Stock Items
    └── List Colors
```

---

## Variables

The collection includes these environment variables:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `base_url` | http://localhost:8000 | API base URL |
| `access_token` | (empty) | JWT access token (auto-populated on login) |
| `refresh_token` | (empty) | JWT refresh token (auto-populated on login) |
| `employee_id` | 2 | Default employee ID for assignment |

---

## Typical Workflow Using Updated Collection

### 1. Authentication
1. Use "Login (Get JWT Token)" - token is saved automatically

### 2. Create Order with Employee Assignment
1. Use "Create Order (Simple)" or "Create Order (Complete)"
2. Include `assigned_to` field in the request

### 3. Or Assign Employee After Creation
1. Create order without `assigned_to`
2. Use "Assign Employee to Order" to assign later

### 4. Employee Views Their Orders
1. Use "Get My Assigned Orders" (returns orders for logged-in employee)
2. Or use "Filter Orders by Assigned Employee" to see another employee's orders

### 5. Employee Reserves Stock
1. Use "Reserve Stock for Order" for each item in the order

### 6. Process Order
1. Use "Start Processing Order"
2. Use "Ship Order" with tracking info

### 7. Complete Fulfillment
1. Use "Adjust Stock (Fulfillment)" with negative quantity to deduct shipped items

### 8. Handle Cancellation
1. Use "Cancel Order"
2. Use "Release Reserved Stock" to free up the reserved stock

---

## Import Instructions

1. Open Postman
2. Click "Import" button
3. Select `POSTMAN_COLLECTION_ORDERS.json`
4. The collection will be imported with all folders and requests
5. Set your environment variables (base_url, employee_id, etc.)
6. Start with "Login (Get JWT Token)" to authenticate

---

## Testing Notes

- All endpoints require JWT authentication (except login endpoints)
- The access token is automatically saved to environment on successful login
- Use the "Get Current User Info" endpoint to verify your authentication
- Remember: Stock is NO LONGER automatically managed - employees must manually reserve/release/adjust stock

---

## Changes from Previous Version

**Added:**
- ✅ Employee Assignment folder (4 endpoints)
- ✅ Manual Stock Management folder (3 endpoints)
- ✅ `assigned_to` field in order creation examples
- ✅ `employee_id` collection variable

**Modified:**
- ✅ Collection description (mentions manual stock management)
- ✅ Cancel Order description (clarifies manual stock release)

**Total Endpoints:** 46 (was 39)

---

## Related Documentation

- See `EMPLOYEE_ORDER_WORKFLOW.md` for complete workflow guide
- See `API_QUICK_REFERENCE.md` for quick API reference
- See `CHANGES_SUMMARY.md` for technical changes
