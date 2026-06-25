# Improvement TODO - 2026-06-23

Source reviewed: `WIMS_SOW_V2.xlsx`

Sheets reviewed:

- `Module Overview`
- `Feature Breakdown`
- `DB - Existing Tables`
- `DB - New Tables`
- `DB - Schema Changes`
- `Courier Booking Rules`
- `Tech Stack`

## Immediate Corrections Needed

- [ ] Update SOW references from old order statuses to current statuses.
  - Old SOW examples mention `PENDING`, `CONFIRMED`, `PROCESSING`, `DELIVERED`.
  - Current approved statuses are `NEW`, `LABEL_PRINTED`, `IN_PROGRESS`, `COMPLETED`, `SHIPPED`, `CANCELLED`.
- [ ] Update SOW references from `available_stock_rolls` to `available_stock_in_mtr`.
- [ ] Reconcile SOW `stock_batches` proposal with current implemented stock batch incoming flow.
  - Current implementation already supports batch id, rolls, meterage, label generation status, and stock meter updates.
  - Remaining SOW gaps are PO linkage, supplier model linkage, and last batch reference.
- [ ] Reconcile SOW `order_items.processing_status` and `quantity_processed` with current implementation.
  - These fields already exist.
  - Current choices include `PENDING`, `IN_PROGRESS`, `PICKED`, `EXCEPTION`, `COMPLETED`.
- [ ] Mark Royal Mail integration as partial until Click & Drop API key is available.
  - Login credentials exist.
  - API booking requires `ROYAL_MAIL_API_KEY`.

## Phase 1 - Stabilize Existing Core

### Dashboard & Reporting

- [ ] Extend dashboard stats into optional drill-down list endpoints.
- [ ] Add dashboard widgets for:
  - orders by channel
  - new orders
  - label printed orders
  - in-progress orders
  - completed orders
  - shipped orders
  - stock in stock
  - low stock
  - out of stock
- [ ] Add `period`, `date_from`, `date_to`, and channel filters consistently across dashboard endpoints.
- [ ] Add exception count once order exception model exists.

### Product & SKU Management

- [ ] Add channel SKU mapping model/API.
  - `channels`
  - `channel_mappings`
- [ ] Add barcode/QR reference fields only if required by mobile processing.
- [ ] Keep existing product import behavior non-duplicating.
- [ ] Keep SKU normalization consistent across:
  - products
  - stock
  - stock batches
  - stock movements
  - order items
  - extended product rows

### Inventory & Stock

- [ ] Add stocktake models and APIs.
  - `stocktakes`
  - `stocktake_items`
- [ ] Add location zone fields.
  - `zone_id`
  - `bin_type`
  - `sort_order`
- [ ] Add warehouse zones model.
  - `warehouse_zones`
- [ ] Add `stock.last_batch_number` if frontend needs quick latest-batch display.
- [ ] Confirm whether stock batches should link to future purchase orders.

## Phase 2 - Stock Inward / Purchase Orders

### Supplier Master

- [ ] Create `purchasing` app.
- [ ] Add `suppliers` model.
- [ ] Add supplier CRUD APIs.
- [ ] Backfill supplier names from stock/product imports where available.
- [ ] Avoid duplicate supplier records by normalized supplier name.

### Purchase Orders

- [ ] Add `purchase_orders` model.
- [ ] Add `po_items` model.
- [ ] Add PO lifecycle:
  - `PENDING`
  - `OPEN`
  - `PARTIAL`
  - `DELIVERED`
  - `CANCELLED`
- [ ] Link incoming stock batches to PO items.
- [ ] Support partial delivery.
- [ ] Update stock meterage only through safe stock movement logs.

## Phase 3 - Multi-Channel Order Ingestion

### Channels

- [ ] Create `channels` app.
- [ ] Add `channels` model.
- [ ] Add `channel_config` or reuse `api_credentials`.
- [ ] Add `ingestion_logs`.
- [ ] Track each import:
  - poll timestamp
  - orders imported
  - orders skipped
  - errors
  - duration
  - status
- [ ] Keep existing Tiaknight import as the first channel adapter.
- [ ] Store raw external status fields separately where useful.
  - Example Tiaknight fields: `order_status_id`, `order_status`, `order_fraud_state_id`.
- [ ] Keep deduplication by `external_order_id`.

### Error Quarantine

- [ ] Add `order_exceptions`.
- [ ] Capture exceptions from:
  - remote order import
  - missing SKU/stock item
  - invalid address
  - courier booking failure
  - tracking sync failure
  - mobile processing discrepancy
- [ ] Add exception list/detail/resolve APIs.

## Phase 4 - Rule Engine

- [ ] Create `rules` app.
- [ ] Add `rules` model with JSON conditions/actions.
- [ ] Add `rule_change_log`.
- [ ] Add rule evaluator service.
- [ ] Add admin/API to manage active/inactive rules.
- [ ] Apply rules during order ingestion for:
  - delivery type
  - priority
  - packaging type
  - courier provider
  - courier service
- [ ] Add deterministic evaluation order by priority.
- [ ] Add tests for all courier booking rules in SOW.

## Phase 5 - Order Batching / Pick Lists / Packing

### Batch Processing

- [ ] Add `order_batches`.
- [ ] Add `batch_orders`.
- [ ] Add nullable `orders.batch_id`.
- [ ] Add batch lifecycle:
  - `PENDING`
  - `PROCESSING`
  - `DISPATCHED`
  - `COMPLETE`
- [ ] Add API to create batches manually.
- [ ] Add scheduled/manual batch generation based on rule outputs.

### Pick Lists

- [ ] Add `pick_lists`.
- [ ] Add `pick_list_items`.
- [ ] Generate pick list sorted by:
  - stock primary location
  - location zone
  - location sort order
- [ ] Add PDF/print output.

### Packing Lists

- [ ] Decide whether packing lists are persisted or generated on demand.
- [ ] Add packing list output using order items and packaging type.

## Phase 6 - Mobile Order Processing / QR

- [ ] Add `qr_codes`.
- [ ] Add `processing_logs`.
- [ ] Generate QR data per order item.
- [ ] Add scan endpoint.
- [ ] Add increment/decrement processed quantity endpoint.
- [ ] Add confirm item endpoint.
- [ ] Add exception reporting endpoint.
- [ ] Ensure parent order status syncs from item completion percentage.
- [ ] Add device/user audit data for every mobile action.

## Phase 7 - Shipping / Courier Integration

### Courier Tables

- [ ] Create `shipping` app.
- [ ] Add `courier_providers`.
- [ ] Add `courier_services`.
- [ ] Add `courier_bookings`.
- [ ] Add `manifests`.
- [ ] Keep existing order fields as quick display fields:
  - `carrier`
  - `tracking_number`
  - `shipping_method`

### Royal Mail

- [ ] Get real `ROYAL_MAIL_API_KEY`.
- [ ] Test `POST /api/v1/orders/{order_id}/book-royal-mail-shipping/` against Royal Mail sandbox/live API.
- [ ] Persist booking response in `courier_bookings` once shipping app exists.
- [ ] Store generated label PDF/ZPL if Royal Mail returns label data.
- [ ] Add manifest flow if required by Click & Drop.

### Other Couriers

- [ ] Add DPD adapter.
- [ ] Add UPS adapter.
- [ ] Add DHL adapter.
- [ ] Add Transglobal adapter.
- [ ] Normalize all adapters behind one booking interface.

## Phase 8 - Tracking Sync

- [ ] Add `tracking_syncs`.
- [ ] Push tracking back to originating channel.
- [ ] Add retry logic.
- [ ] Add failure dashboard.
- [ ] Add manual retry endpoint.
- [ ] Add cron/Celery schedule for pending sync attempts.

## Phase 9 - Returns Management

- [ ] Create `returns` app.
- [ ] Add `returns`.
- [ ] Add `return_items`.
- [ ] Generate RMA number.
- [ ] Add return status lifecycle:
  - `REQUESTED`
  - `APPROVED`
  - `RECEIVED`
  - `RESTOCKED`
  - `REJECTED`
- [ ] If restock is true, create stock movement with type `RETURNED`.

## Phase 10 - Notifications / Audit / Config

### Notifications

- [ ] Add `notifications`.
- [ ] Add notification types:
  - low stock
  - order exception
  - courier failure
  - sync failure
  - PO delivery
  - system
- [ ] Add read/unread APIs.
- [ ] Add notification preferences to accounts profile.

### Audit

- [ ] Add system-wide `audit_log`.
- [ ] Track:
  - auth events
  - permission changes
  - rule changes
  - courier booking changes
  - config changes
- [ ] Keep existing `stock_movements` and `order_status_history` as domain-specific audit logs.

### System Config / Credentials

- [ ] Add `config` app.
- [ ] Add `api_credentials` with encrypted values.
- [ ] Add `system_config`.
- [ ] Move courier/channel secrets out of plain `.env` when UI credential management is ready.
- [ ] Add last-tested timestamp for each credential.

## Production Readiness Improvements

- [ ] Move production DB from SQLite to PostgreSQL.
- [ ] Add Redis.
- [ ] Add Celery or another job scheduler.
- [ ] Add scheduled jobs for:
  - Tiaknight order import
  - channel ingestion
  - tracking sync
  - manifest filing
  - notification generation
- [ ] Add structured logs.
- [ ] Add health check endpoint.
- [ ] Add Docker/Docker Compose deployment.
- [ ] Add backup/restore process.

## High-Risk Areas To Handle Carefully

- [ ] Migrations must be non-destructive.
- [ ] Existing APIs must remain backward compatible.
- [ ] Existing product import must remain duplicate-safe.
- [ ] Existing order status flow must not regress.
- [ ] SKU normalization must not corrupt historical order item data.
- [ ] Stock movements must remain the audit source for stock changes.
- [ ] Royal Mail booking must never mark order shipped if API booking fails.

## Suggested Next Implementation Order

1. Add order exception model/API.
2. Add channels and ingestion logs.
3. Add shipping provider/service/booking tables.
4. Move Royal Mail booking result into `courier_bookings`.
5. Add rule engine models and evaluator.
6. Add order batching and pick list generation.
7. Add PO/supplier workflow.
8. Add mobile QR processing logs.
9. Add tracking sync engine.
10. Add notifications and system-wide audit log.

## Notes From Current Codebase

- Current backend already includes meaningful parts of:
  - authentication
  - products
  - product import
  - stock
  - stock movements
  - stock incoming batches
  - orders
  - order items
  - order status history
  - Tiaknight remote order import
  - Royal Mail integration stub/config check
- Current backend does not yet include:
  - channels app
  - purchasing app
  - rules app
  - shipping app
  - mobile app
  - returns app
  - notifications app
  - config app
  - audit app
