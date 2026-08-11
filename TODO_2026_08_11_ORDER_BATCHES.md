# TODO - Order Batch Creation Workflow

Date: 2026-08-11

## Goal

Add manual order batch creation for filtered orders without disturbing the current order import, order status, label printed, stock, Royal Mail, or Tiaknight flows.

Users should be able to filter orders by source/platform, courier method, order type, and other existing order filters, select multiple orders, create a named batch, open that batch later, and print labels from it.

## Required Workflow

1. User opens Orders list.
2. User applies filters such as:
   - courier method: Standard, Next Day, International, Saturday, Collect in Store, etc.
   - platform/source: Website/Web, Amazon, eBay, Etsy, manual, etc.
   - order type: Retail or Wholesale
   - order status
   - label printed status
   - date range
   - customer/search
3. User selects one or more orders from the filtered result.
4. User clicks `Create Order Batch`.
5. Popup opens with dropdown:
   - Batch 1
   - Batch 2
   - Batch 3
   - Batch 4
   - Batch 5
6. Backend creates system generated batch name:
   - `DDMMYYYY-B1`
   - `DDMMYYYY-B2`
   - `DDMMYYYY-B3`
   - `DDMMYYYY-B4`
   - `DDMMYYYY-B5`
7. User can open `Orders -> Order Batches`.
8. Inside each batch user can see:
   - Orders
   - Labels
   - Details
9. Labels can be printed from selected/open batch.

## Retail / Wholesale Logic

### Wholesale Order

An order is wholesale if any single order item has quantity `>= 20`.

Example:

```text
Order A:
Item 1 quantity = 4
Item 2 quantity = 22

Result: Wholesale
```

### Retail Order

An order is retail if all order items have quantity `< 20`.

Example:

```text
Order B:
Item 1 quantity = 2
Item 2 quantity = 10

Result: Retail
```

## Backend Model Changes

Add new model:

```text
OrderBatch
```

Suggested fields:

```text
id
batch_name
batch_number
batch_date
created_by
created_at
updated_at
filters_snapshot
notes
is_deleted
```

Batch name format:

```text
DDMMYYYY-B{batch_number}
```

Example:

```text
11082026-B1
11082026-B2
```

Add relationship between orders and batch.

Preferred safe option:

```text
OrderBatchOrder
```

Suggested fields:

```text
id
batch
order
created_at
```

Reason:

- keeps existing Order table safer
- allows future history/audit
- avoids breaking current order APIs
- prevents duplicate order entry in same batch using unique constraint

Suggested unique constraint:

```text
unique(batch, order)
```

## API Requirements

### 1. List Orders With Filters

Use/extend existing order list APIs so the frontend can apply all filters before creating a batch.

Required filters:

```text
source
platform
courier_service_code
courier_service_name
order_type=retail|wholesale
order_status
payment_status
lable_printed=true|false
date_from
date_to
search
```

Order type filter should be calculated from order items:

```text
wholesale = any item quantity >= 20
retail = no item quantity >= 20
```

### 2. Create Order Batch

Endpoint suggestion:

```http
POST /api/v1/order-batches/
```

Payload:

```json
{
  "batch_number": 1,
  "order_ids": [101, 102, 103],
  "filters_snapshot": {
    "platform": "web",
    "courier_service_code": "STD",
    "order_type": "retail",
    "date_from": "2026-08-11",
    "date_to": "2026-08-11"
  },
  "notes": "Standard web retail orders"
}
```

Response:

```json
{
  "id": 1,
  "batch_name": "11082026-B1",
  "batch_number": 1,
  "batch_date": "2026-08-11",
  "orders_count": 3,
  "filters_snapshot": {
    "platform": "web",
    "courier_service_code": "STD",
    "order_type": "retail"
  }
}
```

Validation:

- `batch_number` must be 1 to 5.
- `order_ids` must not be empty.
- all orders must exist.
- do not duplicate same order inside same batch.
- decide whether same order can appear in multiple batches. Recommendation: prevent same order from being active in multiple batches unless business approves.

### 3. List Order Batches

Endpoint suggestion:

```http
GET /api/v1/order-batches/
```

Filters:

```text
batch_date
batch_number
batch_name
created_by
date_from
date_to
```

Response should include:

```text
batch id
batch name
batch number
batch date
orders count
labels printed count
created by
created at
filters snapshot
```

### 4. Get Order Batch Details

Endpoint suggestion:

```http
GET /api/v1/order-batches/{id}/
```

Response tabs data:

```text
orders
labels
details
filters_snapshot
```

Orders tab should include same useful order fields:

```text
order id
external order id
customer
status
platform/source
courier method
courier code
total amount
total weight
order date
label printed status
items count
```

Labels tab should include label printing fields:

```text
order
order items
sku
product name
quantity
summary
personalization
sample name
lable_printed
shipping/courier code
```

Details tab should include:

```text
batch metadata
filters used
created by
created at
counts by status
counts by platform
counts by courier code
retail/wholesale counts
```

### 5. Print/Mark Labels For Batch

Endpoint suggestion:

```http
PATCH /api/v1/order-batches/{id}/labels/printed/
```

Payload:

```json
{
  "lable_printed": true,
  "order_item_ids": [1001, 1002, 1003]
}
```

If `order_item_ids` is omitted, decide whether to mark all batch order items as printed.

Recommended behavior:

- if `order_item_ids` provided: update only those items in the batch
- if `order_item_ids` not provided: update all items in the batch

## Frontend/Menu Requirements

Add submenu:

```text
Orders -> Order Batches
```

Order Batches page:

```text
batch list
date filter
batch number filter
search by batch name
open batch action
```

Batch details page:

```text
Tabs:
1. Orders
2. Labels
3. Details
```

Orders page:

```text
Add Create Order Batch button.
Open popup after selecting orders.
Popup has Batch 1 to Batch 5 dropdown.
```

## Existing Flow Safety

Do not change:

```text
Tiaknight import behavior
Royal Mail booking behavior
existing order status logic
existing stock decrement logic
existing label printed endpoint behavior
existing order list/detail response fields unless additive
```

All new behavior should be additive.

## Tests Needed

Add tests for:

```text
retail order detection
wholesale order detection
create batch with selected orders
generated batch name format
duplicate order prevention inside same batch
list batches
batch detail response includes orders/labels/details
batch label printed update
order filtering by order_type
order filtering by courier method
order filtering by platform/source
```

## Postman Updates

Add/update module:

```text
Orders -> Order Batches
```

Requests:

```text
GET List Order Batches
POST Create Order Batch
GET Get Order Batch Detail
PATCH Mark Batch Labels Printed
DELETE Delete/Cancel Order Batch if implemented
```

Also update order list examples with:

```text
order_type=retail
order_type=wholesale
courier_service_code=STD
platform=web
lable_printed=false
```

## Open Questions

1. Can one order be part of multiple active batches?
2. Should batch name be unique per day and batch number?
3. If `11082026-B1` already exists, should backend reject or append another sequence?
4. Should batches have status, for example `Open`, `Labels Printed`, `Completed`, `Cancelled`?
5. Should deleting a batch only remove the grouping, or also affect label printed/order statuses?
6. Should batch creation lock orders from being edited by another user?

## Recommended Implementation Order

1. Add models and migrations.
2. Add serializers.
3. Add service/helper for retail/wholesale classification.
4. Add filters to order list APIs.
5. Add order batch APIs.
6. Add label printed support from batch.
7. Add admin registration.
8. Add tests.
9. Update Postman collection.
10. Update API documentation.

