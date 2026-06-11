# Order Status Flow Changes

## Summary

The order workflow now uses six business statuses:

1. `NEW` - New order created or imported.
2. `LABEL_PRINTED` - Label has been printed for the order.
3. `IN_PROGRESS` - Completion is more than 0% and less than 100%.
4. `COMPLETED` - Completion is exactly 100%.
5. `SHIPPED` - Shipping has been booked through the shipping API/endpoint.
6. `CANCELLED` - Manually selected by admin or via cancel API.

## Data Migration

Migration `orders/migrations/0002_order_status_flow.py` converts existing database rows to the six approved statuses above.

The same conversion is applied to `OrderStatusHistory.from_status` and `OrderStatusHistory.to_status`.

## API Flow

### New Order

New orders default to:

```json
{
  "order_status": "NEW"
}
```

This applies to manual orders, XML imports, and unmapped eBay orders.

### Label Printed

Preferred endpoint:

```http
POST /api/v1/orders/{order_id}/label-printed/
```

Backward-compatible endpoint:

```http
POST /api/v1/orders/{order_id}/confirm/
```

Both now set:

```json
{
  "order_status": "LABEL_PRINTED"
}
```

### In Progress and Completed

The parent order status is automatically synced when an order item is updated:

```http
PATCH /api/v1/order-items/{order_item_id}/update-status/
```

Example:

```json
{
  "processing_status": "PICKED",
  "quantity_processed": 2
}
```

Order status logic:

| Completion percentage | Order status |
| --- | --- |
| `0%` | stays `NEW` or `LABEL_PRINTED` |
| `> 0%` and `< 100%` | `IN_PROGRESS` |
| `100%` | `COMPLETED` |

If `processing_status` is `PICKED` or `COMPLETED` and `quantity_processed` is not sent, the API sets `quantity_processed` to the full line-item quantity.

### Shipped

Shipping is booked through:

```http
POST /api/v1/orders/{order_id}/ship/
```

Example:

```json
{
  "tracking_number": "TRACK123",
  "carrier": "DHL",
  "notes": "Shipping booked"
}
```

The order must be `COMPLETED` before it can become `SHIPPED`.

### Cancelled

Admin or API can cancel an order with:

```http
POST /api/v1/orders/{order_id}/cancel/
```

Example:

```json
{
  "reason": "Customer requested cancellation"
}
```

Orders can be cancelled before shipping. `SHIPPED` and already `CANCELLED` orders cannot be cancelled by this method.

## Status Choices Endpoint

The existing endpoint:

```http
GET /api/v1/orders/statuses/
```

now returns:

```json
{
  "order_statuses": [
    { "value": "NEW", "label": "New" },
    { "value": "LABEL_PRINTED", "label": "Label Printed" },
    { "value": "IN_PROGRESS", "label": "In Progress" },
    { "value": "COMPLETED", "label": "Completed" },
    { "value": "SHIPPED", "label": "Shipped" },
    { "value": "CANCELLED", "label": "Cancelled" }
  ]
}
```

## Stats Endpoint

The order stats response now uses:

```json
{
  "new_orders": 0,
  "label_printed_orders": 0,
  "in_progress_orders": 0,
  "completed_orders": 0,
  "shipped_orders": 0,
  "cancelled_orders": 0
}
```

Previous order stats keys were removed and replaced by the keys above.

## Import Mapping

XML/WIMS imports:

- Paid/payment received orders map to `LABEL_PRINTED`.
- Dispatched/shipped orders map to `SHIPPED`.
- Unknown or new orders map to `NEW`.

eBay imports:

- `Active` maps to `LABEL_PRINTED`.
- `Completed` maps to `SHIPPED`.
- `Cancelled` and `Inactive` map to `CANCELLED`.
- Unknown statuses map to `NEW`.

## Postman

The single complete Postman collection was updated:

```text
POSTMAN_COLLECTION_COMPLETE.json
```

It includes the preferred label printed endpoint and updated status examples.
