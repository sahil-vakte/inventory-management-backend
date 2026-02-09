# Product Location Update Summary

## Overview
The Product model has been successfully updated to support **two locations** instead of one:
- **Primary Location**: Main storage location for the product
- **Secondary Location**: Backup/alternative storage location for the product

## Database Changes

### Migration Applied
- Migration: `products/0004_remove_product_location_product_primary_location_and_more`
- Status: ✅ Applied successfully

### Model Changes (products/models.py)
```python
# BEFORE
location = models.ForeignKey('Location', on_delete=models.SET_NULL, blank=True, null=True, 
                            related_name='products', help_text="Location where the product is stored")

# AFTER
primary_location = models.ForeignKey('Location', on_delete=models.SET_NULL, blank=True, null=True, 
                                     related_name='primary_products', help_text="Primary location where the product is stored")
secondary_location = models.ForeignKey('Location', on_delete=models.SET_NULL, blank=True, null=True, 
                                      related_name='secondary_products', help_text="Secondary/backup location where the product is stored")
```

## API Changes

### Product Endpoints

#### 1. Create Product (POST `/api/v1/products/`)
```json
{
  "vs_parent_id": 1001,
  "vs_child_id": 2001,
  "parent_reference": "FAB-001",
  "child_reference": "FAB-001-RED",
  "parent_product_title": "Premium Fabric",
  "child_product_title": "Premium Fabric - Red",
  "brand": 1,
  "primary_location": "LOC001",
  "secondary_location": "LOC002",
  "rrp_price_inc_vat": 29.99,
  "cost_price_inc_vat": 15.00,
  "vat_rate": 20.00,
  "child_active": true,
  "parent_active": true
}
```

#### 2. Update Product (PATCH `/api/v1/products/{vs_child_id}/`)
```json
{
  "primary_location": "LOC002",
  "secondary_location": "LOC003",
  "rrp_price_inc_vat": 34.99
}
```

#### 3. Get Product (GET `/api/v1/products/{vs_child_id}/`)
Response now includes:
```json
{
  "vs_child_id": 2001,
  "primary_location": {
    "id": "LOC001",
    "name": "Main Warehouse",
    "description": "Primary storage facility"
  },
  "primary_location_id": "LOC001",
  "secondary_location": {
    "id": "LOC002",
    "name": "Secondary Warehouse",
    "description": "Backup storage"
  },
  "secondary_location_id": "LOC002",
  ...
}
```

#### 4. List Products (GET `/api/v1/products/`)
Response includes:
```json
[
  {
    "vs_child_id": 2001,
    "child_reference": "FAB-001-RED",
    "child_product_title": "Premium Fabric - Red",
    "brand_name": "Premium Brand",
    "primary_location": "LOC001",
    "secondary_location": "LOC002",
    ...
  }
]
```

### Order Item Endpoints

Order items automatically retrieve and display product locations:

#### Get Order Details (GET `/api/v1/orders/{order_number}/`)
```json
{
  "order_number": "ORD-20260209-0001",
  "items": [
    {
      "id": 1,
      "product": 2001,
      "sku": "FAB-001-RED",
      "product_name": "Premium Fabric - Red",
      "quantity": 5,
      "unit_price": 29.99,
      "product_primary_location": {
        "id": "LOC001",
        "name": "Main Warehouse",
        "description": "Primary storage facility"
      },
      "product_secondary_location": {
        "id": "LOC002",
        "name": "Secondary Warehouse",
        "description": "Backup storage"
      }
    }
  ]
}
```

#### Get Order Items (GET `/api/v1/order-items/`)
Includes `product_primary_location` and `product_secondary_location` fields for each item.

### Location Endpoints (Unchanged)

Location management endpoints remain the same:
- GET `/api/v1/locations/` - List all locations
- POST `/api/v1/locations/` - Create location
- GET `/api/v1/locations/{id}/` - Get location details
- PUT/PATCH `/api/v1/locations/{id}/` - Update location
- DELETE `/api/v1/locations/{id}/` - Delete location

## Files Updated

### 1. products/models.py
- Replaced `location` field with `primary_location` and `secondary_location`

### 2. products/serializers.py
- **ProductListSerializer**: Shows `primary_location` and `secondary_location` IDs
- **ProductDetailSerializer**: Shows full location objects for both fields
- **ProductCreateUpdateSerializer**: Validates and accepts both location fields

### 3. products/admin.py
- Updated list_display to show `primary_location`
- Updated fieldsets to include both `primary_location` and `secondary_location`

### 4. orders/serializers.py
- **OrderItemSerializer**: Added `product_primary_location` and `product_secondary_location` SerializerMethodFields
- Methods automatically fetch location data from related product

### 5. POSTMAN Collections
- Updated all product-related examples to use `primary_location` and `secondary_location`
- Added documentation for location fields

## Validation Rules

1. **Both locations are optional** - Products can have:
   - No locations (both null)
   - Only primary location
   - Only secondary location
   - Both primary and secondary locations

2. **Location IDs must exist** - If provided, the system validates that the location ID exists in the database

3. **No duplicate validation** - Primary and secondary can be the same location if needed

## Testing

### System Check
```bash
source .venv/bin/activate
python manage.py check
```
Result: ✅ No issues found

### Migration Status
```bash
python manage.py showmigrations products
```
Result:
```
products
 [X] 0001_initial
 [X] 0002_brand_deleted_at_brand_is_deleted_and_more
 [X] 0003_location_and_product_location
 [X] 0004_remove_product_location_product_primary_location_and_more
```

## Usage Examples

### Creating a Product with Locations
```bash
POST /api/v1/products/
{
  "vs_child_id": 3001,
  "child_reference": "PROD-001",
  "child_product_title": "Test Product",
  "primary_location": "LOC001",
  "secondary_location": "LOC002",
  ...
}
```

### Updating Only Primary Location
```bash
PATCH /api/v1/products/3001/
{
  "primary_location": "LOC003"
}
```

### Removing Secondary Location
```bash
PATCH /api/v1/products/3001/
{
  "secondary_location": null
}
```

### Creating an Order
When creating an order, just specify the product ID. The order items response will automatically include the product's primary and secondary locations:

```bash
POST /api/v1/orders/
{
  "customer_email": "customer@example.com",
  "items": [
    {
      "product": 3001,
      "sku": "PROD-001",
      "quantity": 5,
      "unit_price": 29.99
    }
  ]
}
```

Response includes location data in each item.

## Backward Compatibility

⚠️ **Breaking Change**: The old `location` field has been removed and replaced with `primary_location` and `secondary_location`. 

- Any API calls using `"location"` field will no longer work
- Update all client applications to use `"primary_location"` and/or `"secondary_location"`
- The migration has been applied to the database

## Summary

✅ **Completed Changes:**
1. Database model updated with migration applied
2. Product serializers updated for create, update, and read operations
3. Order item serializers show product locations automatically
4. Admin interface updated
5. POSTMAN collections updated with examples
6. System validation passed
7. No errors detected

🎯 **Next Steps:**
- Update any external applications or scripts that reference product locations
- Test all product and order API endpoints
- Verify location data appears correctly in order items
