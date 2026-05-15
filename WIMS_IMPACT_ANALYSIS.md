# WIMS Implementation — Impact Analysis

> This document details exactly how the WIMS implementation TODO affects the existing codebase.  
> Every existing file, endpoint, model, and setting is classified into one of three categories:  
> **Unaffected**, **Affected (modified)**, or **Additive (new only)**.

---

## Quick Summary

| Category | Count | Description |
|---|---|---|
| Unaffected | 26 items | Existing code — zero changes required |
| Affected | 12 items | Existing files that need targeted edits |
| Additive | 35+ items | Brand new — no existing code touched |

---

## 1. UNAFFECTED — No changes required

These files, endpoints, and systems continue to work exactly as they are today. Nothing in the WIMS TODO modifies them.

---

### 1.1 — Existing API Endpoints (all remain intact)

| Endpoint Group | URL Pattern | App |
|---|---|---|
| Products | `GET/POST/PATCH/DELETE /api/v1/products/` | `products` |
| Categories | `GET/POST/PATCH/DELETE /api/v1/categories/` | `products` |
| Brands | `GET/POST/PATCH/DELETE /api/v1/brands/` | `products` |
| Locations | `GET/POST/PATCH/DELETE /api/v1/locations/` | `products` |
| Colors | `GET/POST/PATCH/DELETE /api/v1/colors/` | `colors` |
| Stock Items | `GET/POST/PATCH/DELETE /api/v1/stock/` | `stock` |
| Stock Movements | `GET/POST /api/v1/movements/` | `stock` |
| Orders | `GET/POST/PATCH/DELETE /api/v1/orders/` | `orders` |
| Order Items | `GET/POST/PATCH/DELETE /api/v1/order-items/` | `orders` |
| Order History | `GET /api/v1/order-history/` | `orders` |
| User Types | `GET/POST/PATCH /api/v1/usertypes/` | `accounts` |
| Users | `GET/POST/PATCH /api/v1/users/` | `accounts` |
| Auth Login | `POST /api/v1/auth/login/` | `inventory_management` |
| Auth Refresh | `POST /api/v1/auth/token/refresh/` | `inventory_management` |
| Auth Verify | `POST /api/v1/auth/token/verify/` | `inventory_management` |
| Auth User Info | `GET /api/v1/auth/user/` | `inventory_management` |
| Auth Logout | `POST /api/v1/auth/logout/` | `inventory_management` |
| Auth Register | `POST /api/v1/auth/register/` | `inventory_management` |

**Why unaffected:** New WIMS apps register under entirely new URL prefixes (`/api/v1/warehouse/`, `/api/v1/shipping/`, etc.). No existing `urlpatterns` entry is removed or altered.

---

### 1.2 — Existing Model Logic (all business logic preserved)

| Model | File | What is preserved |
|---|---|---|
| `Order` | `orders/models.py` | `OrderManager`, `save()` auto-numbering, `calculate_totals()`, `soft_delete()`, `restore()`, all existing fields |
| `OrderItem` | `orders/models.py` | All existing fields, FK to `Order`, FK to `Product`/`StockItem` |
| `OrderStatusHistory` | `orders/models.py` | Entire model — not touched |
| `StockItem` | `stock/models.py` | `StockManager`, all existing fields, `sku` primary key, all location FKs |
| `StockMovement` | `stock/models.py` | Entire model — not touched |
| `Location` | `products/models.py` | Auto-ID generation (`LOC001` logic), all existing fields |
| `Product` | `products/models.py` | Entire model — not touched |
| `Category` / `Brand` | `products/models.py` | Entire models — not touched |
| `Color` | `colors/models.py` | Entire model — not touched |
| `UserType` | `accounts/models.py` | `name`, `description` fields — not removed |
| `Profile` | `accounts/models.py` | `user`, `usertype`, `plain_password` fields — not removed |

---

### 1.3 — Existing Serializers, Views, and URL Files

| File | Status |
|---|---|
| `orders/serializers.py` | Unaffected — no removals or renames |
| `orders/views.py` | Unaffected — new viewsets go in new apps |
| `orders/urls.py` | Unaffected — new order sub-routes added separately |
| `products/serializers.py` | Unaffected |
| `products/views.py` | Unaffected |
| `products/urls.py` | Unaffected |
| `stock/serializers.py` | Unaffected |
| `stock/views.py` | Unaffected |
| `stock/urls.py` | Unaffected |
| `accounts/serializers.py` | Unaffected |
| `accounts/views.py` | Unaffected |
| `accounts/urls.py` | Unaffected |
| `colors/` (entire app) | Unaffected — no WIMS changes touch this app |

---

### 1.4 — Existing Infrastructure and Config Files

| File | Status |
|---|---|
| `inventory_management/wsgi.py` | Unaffected — ASGI is added alongside it, not replacing it |
| `inventory_management/auth_views.py` | Unaffected |
| `inventory_management/api_views.py` | Unaffected |
| `manage.py` | Unaffected |
| `db.sqlite3` | Unaffected unless Phase 0.2 (PostgreSQL migration) is executed |
| All existing migrations in `orders/`, `products/`, `stock/`, `accounts/`, `colors/` | Unaffected — new migrations are appended, never replaced |
| `requirements.txt` | Unaffected until Phase 0.1 (new packages appended) |

---

### 1.5 — Existing Data

| Data | Status |
|---|---|
| All existing `orders` rows | Safe — Phase 3 only adds nullable columns |
| All existing `order_items` rows | Safe — new fields have `default=0` and `default='PENDING'` |
| All existing `locations` rows | Safe — new FK is nullable (`null=True`) |
| All existing `stock` rows | Safe — new `last_batch_number` field is nullable |
| All existing `usertype` and `profile` rows | Safe — new fields are nullable JSONFields |

---

## 2. AFFECTED — Existing files that need targeted edits

These files **will be edited** during WIMS implementation. Every change is described precisely so you know what to expect.

---

### 2.1 — `inventory_management/settings.py`

**Phase:** 0.1, 0.3, 0.4, 0.5 and each new app phase

**Changes:**

#### a) `INSTALLED_APPS` — 10 new entries appended (never removed)
```python
# Current INSTALLED_APPS has: accounts, products, colors, stock, orders
# After WIMS these are added (in phase order):
'django_celery_beat',     # Phase 0.4
'channels',               # Phase 0.5 (Django Channels WebSocket lib)
'warehouse',              # Phase 1.1
'config',                 # Phase 1.2
'audit',                  # Phase 1.3
'shipping',               # Phase 2.1
'purchasing',             # Phase 6.1
'sales_channels',         # Phase 7.1 (named sales_channels to avoid conflict with 'channels' above)
'rules',                  # Phase 10.1
'mobile',                 # Phase 11.1
'returns',                # Phase 12.1
'notifications',          # Phase 13.1
```

#### b) `DATABASES` block — replaced (Phase 0.2, optional)
```python
# Current:
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

# Replaced with PostgreSQL block — only do this after dumpdata backup
```
> **Risk level: HIGH** — must `dumpdata` before switching. Can be deferred until production.

#### c) New config blocks appended (non-destructive)
```python
# Redis cache config        — Phase 0.3
# Celery config             — Phase 0.4
# Django Channels config    — Phase 0.5
```
These are pure additions at the bottom of the file — nothing existing is removed.

---

### 2.2 — `inventory_management/urls.py`

**Phase:** Each new app phase (1–13)

**Changes:** New `path()` entries appended to `urlpatterns`. Existing entries are never removed.

```python
# Added (one per new app):
path('api/v1/', include('warehouse.urls')),
path('api/v1/', include('config.urls')),
path('api/v1/', include('audit.urls')),
path('api/v1/', include('shipping.urls')),
path('api/v1/', include('purchasing.urls')),
path('api/v1/', include('sales_channels.urls')),
path('api/v1/', include('rules.urls')),
path('api/v1/', include('mobile.urls')),
path('api/v1/', include('returns.urls')),
path('api/v1/', include('notifications.urls')),
```

**Impact on existing URLs:** Zero — Django URL routing is additive. Existing patterns resolve exactly as before.

---

### 2.3 — `inventory_management/asgi.py`

**Phase:** 0.5 (Django Channels)

**Current state:** Standard Django ASGI file — single-line `get_asgi_application()`.

**Change:** Wrapped with `ProtocolTypeRouter` to support both HTTP and WebSocket. The HTTP route still calls `get_asgi_application()` so all existing views continue to work.

**Impact on existing HTTP endpoints:** Zero — HTTP requests still routed to Django's standard handler.

---

### 2.4 — `products/models.py` — `Location` model

**Phase:** 3.1

**Change:** 3 new fields added to the `Location` class. No existing fields removed, no `save()` logic altered.

```python
# Added to Location model:
zone = ForeignKey('warehouse.WarehouseZone', SET_NULL, null=True, blank=True)
bin_type = CharField(max_length=20, default='PICKING', choices=[...])
sort_order = IntegerField(default=0)
```

**Impact on existing `GET /api/v1/locations/` responses:** New fields appear in responses with their defaults. Existing API clients receive extra keys — no keys are removed.

**Impact on existing `POST /api/v1/locations/` requests:** `zone`, `bin_type`, `sort_order` are all optional — existing payloads continue to work unchanged.

---

### 2.5 — `orders/models.py` — `Order` model

**Phase:** 3.2

**Change:** 6 new fields added. No existing fields removed. Existing `save()`, `calculate_totals()`, `soft_delete()` logic unchanged.

```python
# Added to Order model:
batch = ForeignKey('orders.OrderBatch', SET_NULL, null=True, blank=True)     # added in Phase 4 step
delivery_type = CharField(max_length=30, null=True, blank=True, choices=[...])
priority = IntegerField(default=3)
packaging_type = CharField(max_length=30, null=True, blank=True, choices=[...])
courier_provider = ForeignKey('shipping.CourierProvider', SET_NULL, null=True, blank=True)
courier_service = ForeignKey('shipping.CourierService', SET_NULL, null=True, blank=True)
```

**Impact on existing `GET /api/v1/orders/` responses:** New fields appended. No existing fields removed.

**Impact on existing `POST /api/v1/orders/` requests:** All new fields are optional (nullable or have defaults). Existing order creation payloads work unchanged.

**Impact on existing `OrderManager` / soft delete:** Zero — manager filters on `is_deleted` which is unchanged.

---

### 2.6 — `orders/models.py` — `OrderItem` model

**Phase:** 3.3

**Change:** 2 new fields with safe defaults.

```python
# Added to OrderItem model:
quantity_processed = IntegerField(default=0)
processing_status = CharField(max_length=20, default='PENDING', choices=[...])
```

**Impact:** All existing order items get `quantity_processed=0` and `processing_status='PENDING'` automatically after migration. No breakage.

---

### 2.7 — `stock/models.py` — `StockItem` model

**Phase:** 3.4

**Change:** 1 new nullable field.

```python
# Added to StockItem model:
last_batch_number = CharField(max_length=50, null=True, blank=True)
```

**Impact:** Negligible. Existing stock rows get `NULL` for this field. Existing stock endpoints unaffected.

---

### 2.8 — `accounts/models.py` — `UserType` model

**Phase:** 3.5

**Change:** 1 new nullable JSONField.

```python
# Added to UserType model:
permissions = JSONField(null=True, blank=True)
```

**Impact:** Existing user type rows get `NULL`. Existing `/api/v1/usertypes/` responses gain a `permissions: null` key.

---

### 2.9 — `accounts/models.py` — `Profile` model

**Phase:** 3.5

**Change:** 2 new nullable fields.

```python
# Added to Profile model:
notification_preferences = JSONField(null=True, blank=True)
last_login_ip = CharField(max_length=45, null=True, blank=True)
```

**Impact:** Existing profile rows get `NULL` for both. Existing profile endpoints gain 2 new nullable keys.

---

### 2.10 — `orders/serializers.py` and `products/serializers.py`

**Phase:** 3.1 – 3.3

**Change:** Existing serializers need the new fields added to their `fields` lists (or `exclude` lists updated). No existing field is removed from any serializer.

**Risk:** If serializers use `fields = '__all__'`, new fields appear automatically. If they use explicit field lists, the new fields must be manually added — otherwise they won't appear in API responses even after migration.

---

### 2.11 — `orders/views.py` — `OrderViewSet`

**Phase:** 3.2, 4.x

**Change:** The `get_queryset()` method's `select_related()` call should be updated to include the new `courier_provider`, `courier_service`, and `batch` FKs for query performance. Functionally it still works without this update — Django will just make extra queries.

**No existing filter, action, or permission is changed.**

---

### 2.12 — New migration files in existing apps

**Phase:** 3.1–3.5

**Change:** New migration files are created in the `migrations/` folders of `products`, `orders`, `stock`, and `accounts`. Existing migration files are never edited.

| App | New migration file | What it does |
|---|---|---|
| `products` | `0002_location_zone_bin_type_sort_order.py` | Adds 3 fields to `locations` table |
| `orders` | `0006_order_delivery_type_priority_packaging_...py` | Adds 5 fields to `orders` table |
| `orders` | `0007_order_batch.py` | Adds `batch` FK after `order_batches` table exists |
| `orders` | `0008_orderitem_quantity_processed_processing_status.py` | Adds 2 fields to `order_items` table |
| `stock` | `next_migration_last_batch_number.py` | Adds 1 field to `stock` table |
| `accounts` | `0004_usertype_permissions_profile_notifications.py` | Adds 3 fields across 2 models |

---

## 3. ADDITIVE — Brand new, zero overlap with existing code

Everything in this section is created from scratch. No existing file is touched. Existing tests, endpoints, and data are completely isolated from these.

---

### 3.1 — New Django Apps (10 apps, 35 new tables)

| App | Tables Created | Phase |
|---|---|---|
| `warehouse` | `warehouse_zones` | 1.1 |
| `config` | `api_credentials`, `system_config`, `print_config` | 1.2 / 1.2.1 |
| `audit` | `audit_log` | 1.3 |
| `shipping` | `courier_providers`, `courier_services`, `courier_bookings`, `manifests`, `tracking_syncs`, `shipping_labels`, `print_jobs` | 2.1 / 9.1 / 9.2 |
| `purchasing` | `suppliers`, `purchase_orders`, `po_items` | 6.1 |
| `sales_channels` | `channels`, `channel_mappings`, `ingestion_logs`, `channel_stock_sync_log` | 7.1 / 7.2 |
| `rules` | `rules`, `rule_change_log` | 10.1 |
| `mobile` | `qr_codes`, `processing_logs`, `pick_lists`, `pick_list_items` | 11.1 / 11.2 |
| `returns` | `returns`, `return_items` | 12.1 |
| `notifications` | `notifications` | 13.1 |

---

### 3.2 — New Models in Existing Apps (additive only)

These models are added to existing app `models.py` files but do not alter existing model classes.

| Model | App | Table | Phase |
|---|---|---|---|
| `OrderBatch` | `orders` | `order_batches` | 4.1 |
| `BatchOrder` | `orders` | `batch_orders` | 4.1 |
| `OrderException` | `orders` | `order_exceptions` | 4.2 |
| `OrderNote` | `orders` | `order_notes` | 4.3 |
| `StockBatch` | `stock` | `stock_batches` | 5.1 |
| `Stocktake` | `stock` | `stocktakes` | 5.2 |
| `StocktakeItem` | `stock` | `stocktake_items` | 5.2 |

---

### 3.3 — New API Endpoint Groups (26 new groups)

All under `/api/v1/` — none conflict with existing routes.

| Endpoint Group | Prefix | Phase |
|---|---|---|
| Warehouse Zones | `/api/v1/warehouse/zones/` | 1.1 |
| API Credentials | `/api/v1/config/credentials/` | 1.2 |
| System Config | `/api/v1/config/system/` | 1.2 |
| Printer Config | `/api/v1/config/printers/` | 1.2.1 |
| Audit Logs | `/api/v1/audit/logs/` | 1.3 |
| Courier Providers | `/api/v1/shipping/providers/` | 2.1 |
| Courier Services | `/api/v1/shipping/services/` | 2.1 |
| Order Batches | `/api/v1/orders/batches/` | 4.1 |
| Order Exceptions | `/api/v1/orders/exceptions/` | 4.2 |
| Order Notes | `/api/v1/orders/{id}/notes/` | 4.3 |
| Stock Batches | `/api/v1/stock/batches/` | 5.1 |
| Stocktakes | `/api/v1/stock/stocktakes/` | 5.2 |
| Channel Sync | `/api/v1/stock/sync-channels/` | 7.2 |
| Suppliers | `/api/v1/purchasing/suppliers/` | 6.1 |
| Purchase Orders | `/api/v1/purchasing/purchase-orders/` | 6.1 |
| Channels | `/api/v1/channels/` | 7.1 |
| Channel Mappings | `/api/v1/channels/mappings/` | 7.1 |
| Ingestion Logs | `/api/v1/channels/ingestion-logs/` | 7.1 |
| Stock Sync Logs | `/api/v1/channels/stock-sync-logs/` | 7.2 |
| Courier Bookings | `/api/v1/shipping/bookings/` | 9.1 |
| Manifests | `/api/v1/shipping/manifests/` | 9.1 |
| Tracking Syncs | `/api/v1/shipping/tracking-syncs/` | 9.1 |
| Label Queue | `/api/v1/labels/queue/` | 9.2 |
| Label Print | `/api/v1/labels/print/` | 9.2 |
| Rules | `/api/v1/rules/` | 10.1 |
| QR Codes | `/api/v1/mobile/qr-codes/` | 11.1 |
| Mobile Scan/Process | `/api/v1/mobile/scan/`, `/api/v1/mobile/process/` | 11.1 |
| Pick Lists | `/api/v1/batches/{id}/pick-list/` | 11.2 |
| Returns | `/api/v1/returns/` | 12.1 |
| Notifications | `/api/v1/notifications/` | 13.1 |

---

### 3.4 — New Infrastructure Files (Phase 0)

| File | Purpose | Existing file touched? |
|---|---|---|
| `inventory_management/celery.py` | Celery app instance | No — new file |
| `inventory_management/routing.py` | WebSocket URL routing | No — new file |
| `Dockerfile` | Container build definition | No — new file |
| `docker-compose.yml` | Multi-container dev/prod setup | No — new file |
| `requirements.txt` additions | `psycopg2-binary celery redis channels weasyprint` etc. | Appended only |

---

### 3.5 — New Management Commands (Additive)

| Command | App | Purpose | Phase |
|---|---|---|---|
| `seed_courier_rules` | `rules` | Seeds CR01–CR15 courier routing rules | 14 |

---

## 4. Key Risks and Mitigations

### Risk 1 — PostgreSQL migration (Phase 0.2)
- **Risk:** Running `migrate` against a fresh PostgreSQL DB loses all SQLite data
- **Mitigation:** Always run `python3 manage.py dumpdata --exclude auth.permission --exclude contenttypes > db_backup.json` first, then `loaddata` after migrating
- **Can defer:** Yes — all other phases work fine on SQLite during development

### Risk 2 — Django Channels naming conflict (Phase 0.5 + Phase 7)
- **Risk:** Installing `django-channels` adds `'channels'` to INSTALLED_APPS; naming your sales channels app `channels` will cause an import collision
- **Mitigation:** Use `app_label = 'sales_channels'` in the custom channels app `Meta` class, or name the app folder `sales_channels` from the start
- **Detection:** Will fail loudly at startup with `RuntimeError: Conflicting models`

### Risk 3 — Phase 3 migration order dependency
- **Risk:** Adding `batch` FK to `Order` requires `order_batches` table to exist first — doing it in one migration will fail
- **Mitigation:** Phase 3.2 explicitly splits into two migrations: first add 5 non-FK fields, then add `batch` FK in Phase 4 after `OrderBatch` is created

### Risk 4 — Serializer field list completeness (Phase 3)
- **Risk:** If existing serializers use explicit `fields = [...]` lists, new model fields won't appear in API responses until the serializer is updated
- **Mitigation:** After each Phase 3 migration, check each affected serializer and add the new fields to its `fields` list

---

## 5. Recommended Implementation Order (minimise disruption)

```
Step 1 — Phase 1   Create warehouse, config, audit apps (safest — purely new)
Step 2 — Phase 2   Create shipping foundation (new app, no model changes)
Step 3 — Phase 6   Create purchasing app (new app, no model changes)
Step 4 — Phase 7   Create channels app (new app — watch naming conflict)
Step 5 — Phase 10  Create rules app (new app)
Step 6 — Phase 13  Create notifications app (new app)
Step 7 — Phase 12  Create returns app (new app)
Step 8 — Phase 3   Run existing-table migrations (additive fields — lowest risk)
Step 9 — Phase 4   Add OrderBatch + related models
Step 10 — Phase 5  Add StockBatch + Stocktake models
Step 11 — Phase 9  Complete shipping (CourierBooking, Manifest, ShippingLabel, PrintJob)
Step 12 — Phase 11 Add mobile app + pick lists
Step 13 — Phase 14 Seed CR01–CR15 courier rules
Step 14 — Phase 0  PostgreSQL + Celery + Docker (defer to just before production deployment)
```

> **Rationale:** Phases 1–2, 6–7, 10, 12–13 create entirely new apps with no dependencies on model changes. Doing these first means the system has more new functionality working before any existing model is touched. Phase 3 (model changes) is done only after the new apps it depends on (`warehouse`, `shipping`) already exist, preventing FK migration failures.
