# Order Management System - Documentation

## Overview
The Order Management System has been successfully integrated into the Inventory Management System. This module provides comprehensive order processing, XML upload capabilities, and full order lifecycle management.

## Features Implemented

### ✅ Core Order Management
- **Order Model** with complete customer and shipping information
- **Order Items** tracking with product and stock item references
- **Order Status History** for complete audit trail
- **Soft Delete** support across all order entities
- **Automatic Order Number Generation** (Format: ORD-YYYYMMDD-XXXX)

### ✅ Order Statuses
- PENDING - Initial state when order is created
- CONFIRMED - Order has been confirmed
- PROCESSING - Order is being processed
- SHIPPED - Order has been shipped to customer
- DELIVERED - Order has been delivered
- CANCELLED - Order has been cancelled
- ON_HOLD - Order is temporarily on hold

### ✅ Payment Statuses
- UNPAID - No payment received
- PARTIAL - Partial payment received
- PAID - Full payment received
- REFUNDED - Payment refunded
- FAILED - Payment failed

### ✅ Stock Integration
- **Automatic Stock Reservation** when order items are created
- **Stock Release** when orders are cancelled or items removed
- **Stock Availability Validation** before order creation
- **Movement Tracking** for all order-related stock changes
- **Smart Stock Management**: 
  - `reserved_stock` increments when items added to order
  - `reserved_stock` decrements when order cancelled
  - `stock_reserved` flag tracks reservation status per item
  - Stock automatically released if order fails validation

### ✅ XML Upload & Export
- **Upload XML Orders** via API endpoint
- **Export Orders to XML** format
- **Batch Processing** support for multiple orders
- **Flexible XML Structure** supporting various formats
- **Validation & Error Reporting**

## API Endpoints

### Orders API (`/api/v1/orders/`)

#### List & CRUD Operations
```
GET    /api/v1/orders/              - List all orders (with filters)
POST   /api/v1/orders/              - Create new order
GET    /api/v1/orders/{id}/         - Get order details
PUT    /api/v1/orders/{id}/         - Update order
PATCH  /api/v1/orders/{id}/         - Partial update
DELETE /api/v1/orders/{id}/         - Soft delete order
```

#### Order Workflow Actions
```
POST   /api/v1/orders/{id}/confirm/         - Confirm order
POST   /api/v1/orders/{id}/start-processing/ - Start processing
POST   /api/v1/orders/{id}/ship/            - Mark as shipped
POST   /api/v1/orders/{id}/deliver/         - Mark as delivered
POST   /api/v1/orders/{id}/cancel/          - Cancel order
POST   /api/v1/orders/{id}/restore/         - Restore deleted order
```

#### Order Item Management
```
POST   /api/v1/orders/{id}/add-item/           - Add item to order
DELETE /api/v1/orders/{id}/items/{item_id}/    - Remove item from order
```

#### Special Operations
```
POST   /api/v1/orders/upload-xml/   - Upload orders from XML file
GET    /api/v1/orders/stats/        - Get order statistics
```

### Order Items API (`/api/v1/order-items/`)
```
GET    /api/v1/order-items/         - List all order items
GET    /api/v1/order-items/{id}/    - Get item details
```

### Order Status History API (`/api/v1/order-history/`)
```
GET    /api/v1/order-history/       - List all status changes
GET    /api/v1/order-history/{id}/  - Get history details
```

## Query Parameters

### Filtering
```
?order_status=PENDING              - Filter by order status
?payment_status=PAID               - Filter by payment status
?order_source=XML                  - Filter by order source
?customer_email=example@email.com  - Filter by customer email
?date_from=2026-01-01              - Filter from date
?date_to=2026-01-31                - Filter to date
?min_total=100.00                  - Minimum order total
?max_total=500.00                  - Maximum order total
?include_deleted=true              - Include soft deleted orders
?only_deleted=true                 - Only show deleted orders
```

### Search
```
?search=john                       - Search in order number, customer name, email, phone
```

### Ordering
```
?ordering=-order_date              - Sort by order date (descending)
?ordering=total_amount             - Sort by total amount (ascending)
?ordering=-created_at              - Sort by creation date (descending)
```

## XML Upload Format

### Supported XML Structures

#### Multiple Orders (Recommended)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Orders>
  <Order>
    <!-- Order details here -->
  </Order>
  <Order>
    <!-- Another order -->
  </Order>
</Orders>
```

#### Single Order
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Order>
  <!-- Order details here -->
</Order>
```

### Required Fields
```xml
<CustomerName>John Doe</CustomerName>  <!-- Required -->
<Items>                                <!-- At least one item required -->
  <Item>
    <SKU>PRODUCT-SKU</SKU>            <!-- Required -->
    <ProductName>Product Name</ProductName>  <!-- Required -->
    <Quantity>1</Quantity>             <!-- Required -->
    <UnitPrice>10.00</UnitPrice>      <!-- Required -->
  </Item>
</Items>
```

### Optional Fields

#### Customer Information
```xml
<CustomerInfo>
  <Name>John Doe</Name>
  <Email>john@example.com</Email>
  <Phone>+44 7700 900123</Phone>
  <Company>Company Name</Company>
</CustomerInfo>
```

#### Addresses
```xml
<ShippingAddress>
  <AddressLine1>123 Street</AddressLine1>
  <AddressLine2>Flat 4B</AddressLine2>
  <City>London</City>
  <State>Greater London</State>
  <PostalCode>SW1A 1AA</PostalCode>
  <Country>UK</Country>
</ShippingAddress>

<BillingAddress>
  <!-- Same structure as ShippingAddress -->
</BillingAddress>
```

#### Financial Details
```xml
<Subtotal>100.00</Subtotal>
<TaxRate>20.00</TaxRate>
<TaxAmount>20.00</TaxAmount>
<ShippingCost>5.99</ShippingCost>
<DiscountAmount>10.00</DiscountAmount>
<TotalAmount>115.99</TotalAmount>
```

#### Order Metadata
```xml
<OrderNumber>EXT-2026-001</OrderNumber>
<OrderDate>2026-01-02T10:30:00</OrderDate>
<ExpectedDeliveryDate>2026-01-09T00:00:00</ExpectedDeliveryDate>
<OrderStatus>PENDING</OrderStatus>
<PaymentStatus>PAID</PaymentStatus>
<PaymentMethod>Credit Card</PaymentMethod>
<PaymentReference>PMT-123456</PaymentReference>
<ShippingMethod>Express Delivery</ShippingMethod>
<TrackingNumber>TRACK-123456</TrackingNumber>
<Carrier>DHL</Carrier>
<CustomerNotes>Delivery notes</CustomerNotes>
<InternalNotes>Internal notes</InternalNotes>
```

## Usage Examples

### 1. Upload XML File
```bash
curl -X POST http://localhost:8000/api/v1/orders/upload-xml/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@sample_order.xml"
```

**Response:**
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
    }
  ],
  "errors": []
}
```

### 2. Create Order Manually
```bash
curl -X POST http://localhost:8000/api/v1/orders/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Jane Smith",
    "customer_email": "jane@example.com",
    "items": [
      {
        "sku": "109LT-BK",
        "product_name": "Test Product",
        "quantity": 2,
        "unit_price": "25.00"
      }
    ]
  }'
```

### 3. Confirm an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/confirm/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes": "Order confirmed by customer"}'
```

### 4. Ship an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/ship/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tracking_number": "TRACK-123456",
    "carrier": "DHL",
    "notes": "Shipped via express service"
  }'
```

### 5. Cancel an Order
```bash
curl -X POST http://localhost:8000/api/v1/orders/1/cancel/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Customer requested cancellation"}'
```

**Note:** Cancelling an order will:
- Change order status to `CANCELLED`
- **Automatically release all reserved stock** back to available inventory
- Update `stock_reserved` flag to `false` on all order items
- Create status history entry with cancellation reason
- Cannot be cancelled if already `DELIVERED` or `CANCELLED`

### 6. Get Order Statistics
```bash
curl -X GET http://localhost:8000/api/v1/orders/stats/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response:**
```json
{
  "total_orders": 150,
  "pending_orders": 25,
  "confirmed_orders": 30,
  "processing_orders": 20,
  "shipped_orders": 45,
  "delivered_orders": 25,
  "cancelled_orders": 5,
  "total_revenue": "45250.00",
  "average_order_value": "301.67",
  "unpaid_orders_count": 15,
  "unpaid_orders_value": "4525.00"
}
```

## Django Admin Interface

Access the admin interface at: `http://localhost:8000/admin/`

### Features:
- ✅ Order management with inline items and status history
- ✅ Bulk actions (confirm, ship, cancel, soft delete, restore)
- ✅ Colored status badges for easy visibility
- ✅ Advanced filtering and search
- ✅ Order status history tracking
- ✅ Order item management

## Database Tables Created

- `orders` - Main order table
- `order_items` - Order line items
- `order_status_history` - Status change audit trail

## Automatic Features

### Stock Reservation Workflow

**When Creating an Order:**
1. System validates stock availability for each item
2. If available, `StockItem.reserved_stock` is incremented by order quantity
3. `OrderItem.stock_reserved` flag is set to `True`
4. Stock becomes unavailable for other orders

**When Cancelling an Order:**
1. System iterates through all order items
2. Calls `OrderItem.release_stock()` for each item
3. `StockItem.reserved_stock` is decremented by order quantity
4. `OrderItem.stock_reserved` flag is set to `False`
5. Stock becomes available again for new orders

**When Removing Order Items:**
1. If item has reserved stock, it's automatically released
2. Stock becomes available again
3. Order totals are recalculated

**Stock Fields:**
- `StockItem.available_stock_rolls` - Physical stock in warehouse
- `StockItem.reserved_stock` - Stock reserved for orders
- `StockItem.total_available_stock` - Calculated: available - reserved
- `OrderItem.stock_reserved` - Boolean flag indicating reservation status

### Order Number Generation
Orders automatically receive a unique number in format: `ORD-YYYYMMDD-XXXX`
Example: `ORD-20260102-0001`

### Total Calculation
Order totals are automatically calculated from:
- Subtotal (sum of all line items)
- Tax Amount (based on tax rate)
- Shipping Cost
- Discount Amount

### Stock Management
- Stock is **automatically reserved** when order items are created
- Stock is **automatically released** when:
  - Orders are cancelled
  - Order items are removed
  - Order creation fails validation
- Stock availability is validated before order creation
- Each order item tracks its reservation status with `stock_reserved` flag
- StockItem's `reserved_stock` field accurately reflects all active reservations

### Status History
All status changes are automatically tracked with:
- From/To status
- User who made the change
- Timestamp
- Reason for change

## File Structure

```
orders/
├── __init__.py
├── apps.py
├── models.py              # Order, OrderItem, OrderStatusHistory
├── serializers.py         # All serializers
├── views.py               # OrderViewSet with all actions
├── urls.py                # URL routing
├── admin.py               # Django admin configuration
├── tests.py               # Unit tests
├── services/
│   ├── __init__.py
│   └── xml_parser.py      # XML parsing & export logic
└── migrations/
    ├── __init__.py
    └── 0001_initial.py
```

## Next Steps

1. **Test XML Upload**: Use the provided `sample_order.xml` to test XML upload functionality
2. **Create Test Orders**: Use the API to create orders manually
3. **Test Workflows**: Test order confirmation, shipping, and delivery workflows
4. **Admin Interface**: Explore the Django admin for order management
5. **Integration**: Integrate with your existing stock and product systems

## Support

For issues or questions:
1. Check the API documentation at `/api/v1/`
2. Review error messages in API responses
3. Check Django admin logs
4. Review order status history for audit trail

---

**Order Management System v1.0**  
*Integrated with WIMS Inventory Management*  
*Date: January 2, 2026*
