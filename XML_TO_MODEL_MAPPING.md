# XML to Model Field Mapping

## Overview
This document maps XML fields (both standard and WIMS formats) to the Order and OrderItem models.

---

## ✅ Complete Field Coverage

**YES** - Every field from the XML formats is covered in the Order and OrderItem models.

---

## Order Model Mapping

### Basic Order Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `OrderNumber` | `order/order_reference` | `external_order_id` | Order | External system order ID |
| - | `order/order_id` | `external_order_id` | Order | Alternative WIMS field |
| (auto-generated) | (auto-generated) | `order_number` | Order | Internal order number (ORD-YYYYMMDD-XXXX) |
| `OrderStatus` | `order/order_state` | `order_status` | Order | PENDING/CONFIRMED/PROCESSING/SHIPPED/DELIVERED/CANCELLED |
| `PaymentStatus` | (derived from state) | `payment_status` | Order | UNPAID/PARTIAL/PAID/REFUNDED/FAILED |
| - | - | `order_source` | Order | Set to 'XML' for uploaded orders |

### Customer Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `CustomerInfo/Name` | `customer/billing_firstname + billing_lastname` | `customer_name` | Order | Combined first + last name |
| `CustomerName` | `customer/billing_fullname` | `customer_name` | Order | Fallback format |
| `CustomerInfo/Email` | `customer/billing_email` | `customer_email` | Order | Email address |
| `CustomerEmail` | `customer/email_address` | `customer_email` | Order | Alternative field |
| `CustomerInfo/Phone` | `customer/billing_telephone` | `customer_phone` | Order | Phone number |
| `CustomerPhone` | `customer/billing_mobile` | `customer_phone` | Order | Alternative field |
| `CustomerInfo/Company` | `customer/billing_company_name` | `customer_company` | Order | Company name |
| `CustomerCompany` | - | `customer_company` | Order | Alternative field |

### Billing Address

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `BillingAddress/AddressLine1` | `customer/billing_address1` | `billing_address_line1` | Order | Address line 1 |
| `BillingAddress/AddressLine2` | `customer/billing_address2` | `billing_address_line2` | Order | Address line 2 |
| `BillingAddress/City` | `customer/billing_town` | `billing_city` | Order | City/Town |
| - | `customer/billing_city` | `billing_city` | Order | Alternative WIMS field |
| `BillingAddress/State` | `customer/billing_county` | `billing_state` | Order | State/County |
| `BillingAddress/PostalCode` | `customer/billing_postcode` | `billing_postal_code` | Order | Postal/ZIP code |
| `BillingAddress/Country` | `customer/billing_country_name` | `billing_country` | Order | Country name (default: UK) |

### Shipping Address

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `ShippingAddress/AddressLine1` | `customer/delivery_address1` | `shipping_address_line1` | Order | Address line 1 |
| `ShippingAddress/AddressLine2` | `customer/delivery_address2` | `shipping_address_line2` | Order | Address line 2 |
| `ShippingAddress/City` | `customer/delivery_town` | `shipping_city` | Order | City/Town |
| - | `customer/delivery_city` | `shipping_city` | Order | Alternative WIMS field |
| `ShippingAddress/State` | `customer/delivery_county` | `shipping_state` | Order | State/County |
| `ShippingAddress/PostalCode` | `customer/delivery_postcode` | `shipping_postal_code` | Order | Postal/ZIP code |
| `ShippingAddress/Country` | `customer/delivery_country_name` | `shipping_country` | Order | Country name (default: UK) |

### Dates

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `OrderDate` | `order/order_date` | `order_date` | Order | Order creation date |
| `ExpectedDeliveryDate` | `order/dispatch_date` | `expected_delivery_date` | Order | Expected delivery date |
| - | - | `confirmed_date` | Order | Auto-set when order confirmed |
| - | - | `shipped_date` | Order | Auto-set when order shipped |
| - | - | `delivered_date` | Order | Auto-set when order delivered |

### Financial Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `Subtotal` | `order/product_total_ex` | `subtotal` | Order | Sum of line items before tax |
| `TaxAmount` | `order/grand_total_vat` | `tax_amount` | Order | Total tax amount |
| `TaxRate` | - | `tax_rate` | Order | Tax rate % (default: 20.00) |
| `ShippingCost` | `order/shipping_total_ex` | `shipping_cost` | Order | Shipping/delivery cost |
| `DiscountAmount` | `order/discount_ex` | `discount_amount` | Order | Total discount applied |
| `TotalAmount` | `order/grand_total_inc` | `total_amount` | Order | Final total inc tax & shipping |

### Payment Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `PaymentMethod` | `payment/payment_type` | `payment_method` | Order | E.g., Credit Card, PayPal |
| `PaymentReference` | `payment/transaction_reference` | `payment_reference` | Order | Payment transaction ID |

### Shipping Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `ShippingMethod` | `order/courier_name` | `shipping_method` | Order | Shipping method/carrier |
| `TrackingNumber` | - | `tracking_number` | Order | Tracking number |
| `Carrier` | `order/courier_name` | `carrier` | Order | Carrier/courier name |

### Notes

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `CustomerNotes` | `order/order_customer_comments` | `customer_notes` | Order | Notes from customer |
| `InternalNotes` | `order/order_notes` | `internal_notes` | Order | Internal staff notes |

### User Tracking (Auto-populated)

| XML Field | Model Field | Model | Notes |
|-----------|-------------|-------|-------|
| - | `created_by` | Order | User who uploaded XML |
| - | `updated_by` | Order | Last user to update order |
| - | `assigned_to` | Order | **NEW** - Employee assigned to order |

### Soft Delete (Auto-managed)

| XML Field | Model Field | Model | Notes |
|-----------|-------------|-------|-------|
| - | `is_deleted` | Order | Soft delete flag |
| - | `deleted_at` | Order | Deletion timestamp |
| - | `deleted_by` | Order | User who deleted order |

### Timestamps (Auto-managed)

| XML Field | Model Field | Model | Notes |
|-----------|-------------|-------|-------|
| - | `created_at` | Order | Record creation timestamp |
| - | `updated_at` | Order | Last update timestamp |

---

## OrderItem Model Mapping

### Item Information

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `Item/SKU` | `product/reference` | `sku` | OrderItem | Stock keeping unit |
| `Item/ProductName` | `product/title` | `product_name` | OrderItem | Product name at order time |
| `Item/ProductType` | (auto-filled from stock) | `product_type` | OrderItem | Product type code |
| `Item/ColorCode` | (auto-filled from stock) | `color_code` | OrderItem | Color code |

### Quantity & Pricing

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `Item/Quantity` | `product/quantity` | `quantity` | OrderItem | Quantity ordered |
| `Item/UnitPrice` | `product/price_inc` | `unit_price` | OrderItem | Price per unit |
| `Item/LineTotal` | (calculated) | `line_total` | OrderItem | Total for this line |
| `Item/TaxRate` | `product/tax_rate` | `tax_rate` | OrderItem | Tax rate % (default: 20.00) |
| `Item/DiscountAmount` | - | `discount_amount` | OrderItem | Discount for this item |

### Additional Info

| XML Field (Standard) | XML Field (WIMS) | Model Field | Model | Notes |
|---------------------|------------------|-------------|-------|-------|
| `Item/Notes` | - | `notes` | OrderItem | Item-specific notes |

### References (Auto-linked)

| XML Field | Model Field | Model | Notes |
|-----------|-------------|-------|-------|
| - | `order` | OrderItem | ForeignKey to Order |
| - | `product` | OrderItem | ForeignKey to Product (optional) |
| - | `stock_item` | OrderItem | ForeignKey to StockItem (optional, auto-linked by SKU) |

### Timestamps (Auto-managed)

| XML Field | Model Field | Model | Notes |
|-----------|-------------|-------|-------|
| - | `created_at` | OrderItem | Record creation timestamp |
| - | `updated_at` | OrderItem | Last update timestamp |

---

## Fields Removed (Manual Stock Management)

These fields were removed as part of the employee workflow update:

| Old Field | Model | Reason |
|-----------|-------|--------|
| ~~`stock_reserved`~~ | ~~OrderItem~~ | Removed - manual stock management |
| ~~`stock_fulfilled`~~ | ~~OrderItem~~ | Removed - manual stock management |

---

## Auto-Population Logic

The XML parser includes smart auto-population:

1. **Stock Item Lookup**: If SKU exists in stock database:
   - Auto-fills `product_type`, `color_code`, `product_name`
   - Links to `stock_item` and `product` if available
   - Uses `unit_cost` from stock if unit_price is 0

2. **Billing = Shipping**: If billing address is empty, copies from shipping address

3. **Date Validation**: Ignores invalid dates like '0000-00-00 00:00:00'

4. **Status Mapping (WIMS)**:
   - "payment received" or "paid" → `CONFIRMED` status + `PAID` payment
   - "dispatch" or "ship" → `SHIPPED` status

5. **Calculation**: If `total_amount` is 0, calls `calculate_totals()` to compute from items

---

## Supported XML Formats

### 1. Standard Format
```xml
<Orders>
  <Order>
    <OrderNumber>...</OrderNumber>
    <CustomerInfo>...</CustomerInfo>
    <Items>...</Items>
  </Order>
</Orders>
```

### 2. WIMS Format
```xml
<web_orders>
  <web_order>
    <order>...</order>
    <customer>...</customer>
    <payment>...</payment>
    <products>...</products>
  </web_order>
</web_orders>
```

### 3. Single Order
```xml
<Order>
  ...
</Order>
```

---

## Summary

✅ **All XML fields are mapped** to Order or OrderItem models
✅ **Both standard and WIMS formats** are fully supported
✅ **Auto-population** fills missing fields from stock database
✅ **Flexible parsing** handles variations in XML structure
✅ **Smart defaults** for missing optional fields
✅ **New employee assignment** field added to Order model

**No unmapped fields** - The system can handle all data from both XML formats.
