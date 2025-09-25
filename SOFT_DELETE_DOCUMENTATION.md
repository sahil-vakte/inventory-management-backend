# Soft Delete Implementation Documentation

## Overview

This Django inventory management system now includes comprehensive soft delete functionality for all models. Soft delete allows records to be marked as deleted without physically removing them from the database, enabling data recovery and audit trails.

## Models Enhanced with Soft Delete

All models across three apps now support soft delete:

### Colors App
- **Color** - Color definitions with codes and names

### Products App
- **Category** - Product categories with hierarchical support
- **Brand** - Brand information
- **Product** - Main product catalog with 85+ fields

### Stock App
- **StockItem** - Inventory items with stock levels
- **StockMovement** - Stock transaction history

## Implementation Details

### Database Fields Added

Each model now includes:
- `is_deleted` (BooleanField, default=False) - Soft delete flag
- `deleted_at` (DateTimeField, null=True, blank=True) - Deletion timestamp

### Custom Managers

Each model has two managers:
- `objects` (SoftDeleteManager) - Returns only non-deleted records
- `all_objects` (DefaultManager) - Returns all records including deleted ones

```python
# Examples
Color.objects.all()      # Only active colors
Color.all_objects.all()  # All colors including deleted
```

### Model Methods

Each model includes these methods:
- `soft_delete()` - Mark record as deleted
- `restore()` - Restore soft-deleted record  
- `hard_delete()` - Permanently delete record

```python
# Examples
color = Color.objects.get(id=1)
color.soft_delete()  # Mark as deleted
color.restore()      # Restore the record
color.hard_delete()  # Permanently delete
```

## API Endpoints

### Query Parameters for All Endpoints

All ViewSets support these query parameters:

- `include_deleted=true` - Include soft-deleted records in results
- `only_deleted=true` - Return only soft-deleted records
- `force_delete=true` - Permanently delete when using DELETE method

### CRUD Operations

#### List/Retrieve
```
GET /api/v1/colors/                    # Only active records
GET /api/v1/colors/?include_deleted=true   # Include deleted records  
GET /api/v1/colors/?only_deleted=true      # Only deleted records
```

#### Soft Delete
```
DELETE /api/v1/colors/1/               # Soft delete (default)
DELETE /api/v1/colors/1/?force_delete=true  # Hard delete (permanent)
```

#### Restore
```
POST /api/v1/colors/1/restore/         # Restore soft-deleted record
```

## Admin Interface

### Enhanced Admin Features

All admin interfaces include:
- `is_deleted` field in list_display
- `is_deleted` filter in list_filter
- `deleted_at` in readonly_fields
- Custom admin actions for bulk operations

### Admin Actions Available

1. **Soft Delete Selected** - Soft delete multiple records
2. **Restore Selected** - Restore multiple deleted records  
3. **Hard Delete Selected** - Permanently delete soft-deleted records

### Admin Behavior

- Admin interfaces show ALL records (including deleted) for complete visibility
- Deleted records are clearly marked with the `is_deleted` column
- Admins can perform bulk operations using admin actions

## API Examples

### Colors API

```bash
# List active colors
curl -X GET http://127.0.0.1:8000/api/v1/colors/

# List all colors including deleted
curl -X GET http://127.0.0.1:8000/api/v1/colors/?include_deleted=true

# Soft delete a color
curl -X DELETE http://127.0.0.1:8000/api/v1/colors/1/

# Restore a soft-deleted color
curl -X POST http://127.0.0.1:8000/api/v1/colors/1/restore/

# Hard delete (permanent)
curl -X DELETE http://127.0.0.1:8000/api/v1/colors/1/?force_delete=true
```

### Products API

```bash
# List active products with filtering
curl -X GET http://127.0.0.1:8000/api/v1/products/?active_only=true

# Search products including deleted ones
curl -X GET "http://127.0.0.1:8000/api/v1/products/?search=laptop&include_deleted=true"

# Soft delete a product
curl -X DELETE http://127.0.0.1:8000/api/v1/products/1/

# Bulk upload products from Excel
curl -X POST http://127.0.0.1:8000/api/v1/products/upload_excel/ \
  -F "file=@products.xlsx"
```

### Stock API

```bash
# List stock items with low stock alert
curl -X GET http://127.0.0.1:8000/api/v1/stock/items/?low_stock=true

# View stock movements history including deleted
curl -X GET http://127.0.0.1:8000/api/v1/stock/movements/?include_deleted=true

# Adjust stock levels
curl -X POST http://127.0.0.1:8000/api/v1/stock/items/1/adjust_stock/ \
  -H "Content-Type: application/json" \
  -d '{"quantity": 100, "reason": "New shipment", "reference": "PO-2024-001"}'
```

## Database Migrations

The soft delete functionality was added through migrations:

```
colors/migrations/0002_color_deleted_at_color_is_deleted.py
products/migrations/0002_brand_deleted_at_brand_is_deleted_and_more.py  
stock/migrations/0002_stockitem_deleted_at_stockitem_is_deleted_and_more.py
```

## Benefits

1. **Data Recovery** - Accidentally deleted records can be restored
2. **Audit Trail** - Complete history of deletions with timestamps
3. **Referential Integrity** - Related records remain accessible
4. **Compliance** - Meets requirements for data retention policies
5. **Performance** - Queries automatically exclude deleted records
6. **Flexibility** - Option to include deleted records when needed

## Technical Notes

### Foreign Key Relationships

When a record is soft-deleted:
- Related records are NOT automatically soft-deleted
- Foreign key relationships remain intact
- Queries can still access related data if needed

### Performance Considerations

- Default queries automatically filter out deleted records
- Database indexes should include `is_deleted` field for optimal performance
- Consider periodic hard deletion of old soft-deleted records

### Testing

All soft delete functionality can be tested through:
1. Django Admin interface at http://127.0.0.1:8000/admin/
2. API endpoints using curl or Postman
3. Django shell for direct model manipulation

## Future Enhancements

Potential improvements to consider:
1. Automated cleanup of old soft-deleted records
2. Soft delete cascading for related models
3. Detailed audit logging of who deleted what and when
4. Bulk restore functionality in admin interface
5. API endpoints for bulk soft delete/restore operations

## Security Notes

- All API endpoints require authentication (`IsAuthenticated` permission)
- Hard delete operations should be restricted to administrators
- Consider implementing additional permissions for restore operations
- Audit all deletion operations for security compliance

---

**Server Status**: ✅ Django development server running at http://127.0.0.1:8000/
**Database**: SQLite with all migrations applied successfully
**Admin Access**: http://127.0.0.1:8000/admin/