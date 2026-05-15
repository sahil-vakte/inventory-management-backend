# WIMS Implementation TODO

> Base URL for all endpoints: `http://localhost:8000/api/v1/`  
> All requests require: `Authorization: Bearer <access_token>`  
> All list endpoints support: `?page=1&page_size=20`

---

## Dependency Order (must follow this sequence)

```
Phase 0  → Infrastructure setup               (PostgreSQL, Redis, Celery, Django Channels, Docker)
Phase 1  → warehouse, config, audit           (no inter-app deps)
Phase 2  → shipping (providers + services)    (needs config.api_credentials)
Phase 3  → Migrate existing tables            (needs warehouse_zones, courier_providers, courier_services)
Phase 4  → orders new models                  (needs Phase 3 migrations done)
Phase 5  → stock new models                   (needs purchasing.suppliers, purchase_orders)
Phase 6  → purchasing (suppliers, POs)        (no extra deps — can run parallel with Phase 4+5)
Phase 7  → channels (+ ChannelStockSyncLog)   (needs config.api_credentials, products, orders)
Phase 8  → purchasing po_items                (needs purchasing.purchase_orders, products, stock)
Phase 9  → shipping completion                (needs orders, channels; + ShippingLabel, PrintJob)
Phase 10 → rules                              (needs auth_user only)
Phase 11 → mobile (+ Phase 11.2 pick lists)  (needs order_items, orders.OrderBatch)
Phase 12 → returns                            (needs orders, order_items)
Phase 13 → notifications                      (needs auth_user only)
Phase 14 → seed courier booking rules         (CR01–CR15 seed data, needs Phase 10 + Phase 2 done)
```

---

## Phase 0 — Infrastructure Setup

### 0.1 — Python dependencies

#### Tasks
- [ ] Activate virtual environment: `source venv/bin/activate`
- [ ] Install new packages:
  ```bash
  pip install psycopg2-binary celery redis django-celery-beat channels channels-redis python-qrcode Pillow weasyprint
  pip freeze > requirements.txt
  ```

---

### 0.2 — PostgreSQL setup

#### Tasks
- [ ] Install PostgreSQL (if not already): `brew install postgresql@15`
- [ ] Create database and user:
  ```sql
  CREATE DATABASE wims_db;
  CREATE USER wims_user WITH PASSWORD 'your_secure_password';
  GRANT ALL PRIVILEGES ON DATABASE wims_db TO wims_user;
  ```
- [ ] Export current SQLite data:
  ```bash
  python3 manage.py dumpdata --exclude auth.permission --exclude contenttypes > db_backup.json
  ```
- [ ] Update `inventory_management/settings.py`:
  ```python
  DATABASES = {
      'default': {
          'ENGINE': 'django.db.backends.postgresql',
          'NAME': 'wims_db',
          'USER': 'wims_user',
          'PASSWORD': 'your_secure_password',
          'HOST': 'localhost',
          'PORT': '5432',
      }
  }
  ```
- [ ] Run migrations against PostgreSQL: `python3 manage.py migrate`
- [ ] Load data back: `python3 manage.py loaddata db_backup.json`

---

### 0.3 — Redis setup

#### Tasks
- [ ] Install Redis: `brew install redis`
- [ ] Start Redis service: `brew services start redis`
- [ ] Add to `settings.py`:
  ```python
  REDIS_URL = 'redis://localhost:6379/0'
  CACHES = {
      'default': {
          'BACKEND': 'django.core.cache.backends.redis.RedisCache',
          'LOCATION': REDIS_URL,
      }
  }
  ```

---

### 0.4 — Celery setup

#### Tasks
- [ ] Create `inventory_management/celery.py`:
  ```python
  import os
  from celery import Celery

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_management.settings')
  app = Celery('inventory_management')
  app.config_from_object('django.conf:settings', namespace='CELERY')
  app.autodiscover_tasks()
  ```
- [ ] Update `inventory_management/__init__.py`:
  ```python
  from .celery import app as celery_app
  __all__ = ('celery_app',)
  ```
- [ ] Add to `settings.py`:
  ```python
  CELERY_BROKER_URL = 'redis://localhost:6379/0'
  CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
  CELERY_ACCEPT_CONTENT = ['json']
  CELERY_TASK_SERIALIZER = 'json'
  CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
  ```
- [ ] Add `'django_celery_beat'` to `INSTALLED_APPS`
- [ ] `python3 manage.py migrate` (creates celery_beat tables)

#### Celery tasks required (stubs — implement in respective app phases)
- `channels.tasks.poll_channel_orders` — scheduled every `poll_interval_mins` per channel (M06)
- `orders.tasks.auto_create_batch` — scheduled task for auto batch creation (M10)
- `shipping.tasks.file_manifest` — end-of-day manifest filing (M14)
- `shipping.tasks.sync_tracking` — retry failed tracking syncs (M15)

---

### 0.5 — Django Channels (WebSocket) setup

#### Tasks
- [ ] Add `'channels'` to `INSTALLED_APPS` **before** your custom sales channels app (use `app_label = 'sales_channels'` in your custom channels app Meta — see Phase 7 note)
- [ ] Update `inventory_management/asgi.py`:
  ```python
  import os
  from django.core.asgi import get_asgi_application
  from channels.routing import ProtocolTypeRouter, URLRouter
  from channels.auth import AuthMiddlewareStack
  import inventory_management.routing

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_management.settings')
  application = ProtocolTypeRouter({
      'http': get_asgi_application(),
      'websocket': AuthMiddlewareStack(
          URLRouter(inventory_management.routing.websocket_urlpatterns)
      ),
  })
  ```
- [ ] Create `inventory_management/routing.py`:
  ```python
  from django.urls import re_path
  # WebSocket consumers added in Phase 11 (mobile dashboard real-time updates)
  websocket_urlpatterns = []
  ```
- [ ] Add to `settings.py`:
  ```python
  ASGI_APPLICATION = 'inventory_management.asgi.application'
  CHANNEL_LAYERS = {
      'default': {
          'BACKEND': 'channels_redis.core.RedisChannelLayer',
          'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
      }
  }
  ```

---

### 0.6 — Docker setup (optional for dev, required for production)

#### Tasks
- [ ] Create `Dockerfile`:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["gunicorn", "inventory_management.asgi:application", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
  ```
- [ ] Create `docker-compose.yml`:
  ```yaml
  version: '3.9'
  services:
    db:
      image: postgres:15
      environment:
        POSTGRES_DB: wims_db
        POSTGRES_USER: wims_user
        POSTGRES_PASSWORD: your_secure_password
      volumes:
        - postgres_data:/var/lib/postgresql/data
    redis:
      image: redis:7-alpine
    web:
      build: .
      command: gunicorn inventory_management.asgi:application -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
      volumes:
        - .:/app
      ports:
        - "8000:8000"
      depends_on:
        - db
        - redis
      environment:
        DATABASE_URL: postgresql://wims_user:your_secure_password@db:5432/wims_db
        REDIS_URL: redis://redis:6379/0
    celery:
      build: .
      command: celery -A inventory_management worker -l info
      volumes:
        - .:/app
      depends_on:
        - db
        - redis
    celery-beat:
      build: .
      command: celery -A inventory_management beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
      volumes:
        - .:/app
      depends_on:
        - db
        - redis
  volumes:
    postgres_data:
  ```
- [ ] Add `gunicorn uvicorn[standard]` to `requirements.txt`

---

## Phase 1 — Foundation Apps

### 1.1 — `warehouse` app

#### Tasks
- [ ] `python3 manage.py startapp warehouse`
- [ ] Add `'warehouse'` to `INSTALLED_APPS` in `inventory_management/settings.py`
- [ ] Create `warehouse/models.py` — `WarehouseZone` model
- [ ] Create `warehouse/serializers.py`
- [ ] Create `warehouse/views.py` — `WarehouseZoneViewSet`
- [ ] Create `warehouse/urls.py`
- [ ] Register `path('api/v1/', include('warehouse.urls'))` in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations warehouse`
- [ ] `python3 manage.py migrate`

#### Model: `WarehouseZone`
```python
# db_table = 'warehouse_zones'
name = CharField(max_length=100)
zone_type = CharField(max_length=30, choices=[PICKING, BACKSTOCK, RETURNS, RESTRICTED, DISPATCH])
description = TextField(blank=True, null=True)
is_active = BooleanField(default=True)
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/warehouse/zones/`
```json
// Request
{
  "name": "Main Picking Floor",
  "zone_type": "PICKING",
  "description": "Ground floor picking zone"
}

// Response 201
{
  "id": 1,
  "name": "Main Picking Floor",
  "zone_type": "PICKING",
  "description": "Ground floor picking zone",
  "is_active": true,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/warehouse/zones/`
```json
// Response 200
{
  "count": 3,
  "results": [
    { "id": 1, "name": "Main Picking Floor", "zone_type": "PICKING", "is_active": true },
    { "id": 2, "name": "Returns Bay", "zone_type": "RETURNS", "is_active": true },
    { "id": 3, "name": "Dispatch Area", "zone_type": "DISPATCH", "is_active": true }
  ]
}
```

**GET** `/api/v1/warehouse/zones/{id}/`
```json
// Response 200
{
  "id": 1,
  "name": "Main Picking Floor",
  "zone_type": "PICKING",
  "description": "Ground floor picking zone",
  "is_active": true,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**PATCH** `/api/v1/warehouse/zones/{id}/`
```json
// Request
{ "is_active": false }

// Response 200
{ "id": 1, "name": "Main Picking Floor", "zone_type": "PICKING", "is_active": false, ... }
```

**DELETE** `/api/v1/warehouse/zones/{id}/` → `204 No Content`

---

### 1.2 — `config` app

#### Tasks
- [ ] `python3 manage.py startapp config`
- [ ] Add `'config'` to `INSTALLED_APPS`
- [ ] Create `config/models.py` — `ApiCredential`, `SystemConfig` models
- [ ] Create `config/serializers.py` — **mask `api_key_encrypted` and `api_secret_encrypted` in read responses**
- [ ] Create `config/views.py` — `ApiCredentialViewSet`, `SystemConfigViewSet`
- [ ] Create `config/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations config && python3 manage.py migrate`

#### Model: `ApiCredential`
```python
# db_table = 'api_credentials'
provider = CharField(max_length=50)          # e.g. "EBAY", "ROYAL_MAIL"
provider_type = CharField(max_length=20, choices=[CHANNEL, COURIER])
api_key_encrypted = TextField()
api_secret_encrypted = TextField()
oauth_tokens = JSONField(null=True, blank=True)
sandbox_mode = BooleanField(default=False)
is_active = BooleanField(default=True)
last_tested_at = DateTimeField(null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `SystemConfig`
```python
# db_table = 'system_config'
config_key = CharField(max_length=100, unique=True)
config_value = TextField()
description = CharField(max_length=200, null=True, blank=True)
updated_by = ForeignKey(User, SET_NULL, null=True, blank=True)
updated_at = DateTimeField(auto_now=True)
```

#### Endpoints

**POST** `/api/v1/config/credentials/`
```json
// Request
{
  "provider": "ROYAL_MAIL",
  "provider_type": "COURIER",
  "api_key_encrypted": "rmk_live_xxxxxxxxxxxx",
  "api_secret_encrypted": "rms_live_xxxxxxxxxxxx",
  "sandbox_mode": false
}

// Response 201
{
  "id": 1,
  "provider": "ROYAL_MAIL",
  "provider_type": "COURIER",
  "api_key_encrypted": "***MASKED***",
  "api_secret_encrypted": "***MASKED***",
  "sandbox_mode": false,
  "is_active": true,
  "last_tested_at": null,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/config/credentials/` → returns list with keys masked  
**GET** `/api/v1/config/credentials/{id}/` → single record, keys masked  
**DELETE** `/api/v1/config/credentials/{id}/` → `204 No Content`

**POST** `/api/v1/config/system/`
```json
// Request
{
  "config_key": "default_currency",
  "config_value": "GBP",
  "description": "Default currency for all transactions"
}

// Response 201
{
  "id": 1,
  "config_key": "default_currency",
  "config_value": "GBP",
  "description": "Default currency for all transactions",
  "updated_by": null,
  "updated_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/config/system/` → list all key-value settings  
**PATCH** `/api/v1/config/system/{id}/`
```json
// Request
{ "config_value": "USD" }
// Response 200 — updated record
```

---

### 1.2.1 — `PrintConfig` model (add to `config` app)

#### Tasks
- [ ] Add `PrintConfig` model to `config/models.py`
- [ ] Add `PrintConfigViewSet` to `config/views.py`
- [ ] Register endpoints in `config/urls.py`
- [ ] Run `python3 manage.py makemigrations config && python3 manage.py migrate`

#### Model: `PrintConfig`
```python
# db_table = 'print_config'
printer_name = CharField(max_length=100)
printer_type = CharField(max_length=20, choices=[('LABEL', 'Label'), ('DOCUMENT', 'Document'), ('ZPL', 'ZPL Thermal')])
ip_address = CharField(max_length=45, null=True, blank=True)
port = IntegerField(null=True, blank=True)
is_default = BooleanField(default=False)
is_active = BooleanField(default=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Endpoints

**POST** `/api/v1/config/printers/`
```json
// Request
{
  "printer_name": "Zebra ZD420 Label Printer",
  "printer_type": "ZPL",
  "ip_address": "192.168.1.50",
  "port": 9100,
  "is_default": true
}

// Response 201
{
  "id": 1,
  "printer_name": "Zebra ZD420 Label Printer",
  "printer_type": "ZPL",
  "ip_address": "192.168.1.50",
  "port": 9100,
  "is_default": true,
  "is_active": true,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/config/printers/`
```json
// Response 200
{
  "count": 2,
  "results": [
    { "id": 1, "printer_name": "Zebra ZD420 Label Printer", "printer_type": "ZPL", "is_default": true, "is_active": true },
    { "id": 2, "printer_name": "HP LaserJet Document", "printer_type": "DOCUMENT", "is_default": false, "is_active": true }
  ]
}
```

**PATCH** `/api/v1/config/printers/{id}/`
```json
// Request
{ "is_default": true }
// Response 200 — updated record (previous default automatically unset)
```

**DELETE** `/api/v1/config/printers/{id}/` → `204 No Content`

---

### 1.3 — `audit` app

#### Tasks
- [ ] `python3 manage.py startapp audit`
- [ ] Add `'audit'` to `INSTALLED_APPS`
- [ ] Create `audit/models.py` — `AuditLog` model (insert-only, no update/delete via API)
- [ ] Create `audit/serializers.py`
- [ ] Create `audit/views.py` — read-only `AuditLogViewSet` (list + retrieve only)
- [ ] Create `audit/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations audit && python3 manage.py migrate`

#### Model: `AuditLog`
```python
# db_table = 'audit_log'
user = ForeignKey(User, SET_NULL, null=True, blank=True)
action = CharField(max_length=50)          # e.g. CREATE, UPDATE, DELETE, LOGIN
entity_type = CharField(max_length=50)     # e.g. "order", "stock_item"
entity_id = CharField(max_length=50)       # PK of the affected record
before_state = JSONField(null=True, blank=True)
after_state = JSONField(null=True, blank=True)
ip_address = CharField(max_length=45, null=True, blank=True)
timestamp = DateTimeField(auto_now_add=True)
```

#### Endpoints (read-only)

**GET** `/api/v1/audit/logs/`
```json
// Supports filters: ?entity_type=order&entity_id=123&user_id=5
// Response 200
{
  "count": 42,
  "results": [
    {
      "id": 1,
      "user": { "id": 2, "username": "admin" },
      "action": "UPDATE",
      "entity_type": "order",
      "entity_id": "ORD-20260503-0001",
      "before_state": { "order_status": "PENDING" },
      "after_state": { "order_status": "CONFIRMED" },
      "ip_address": "192.168.1.10",
      "timestamp": "2026-05-03T11:00:00Z"
    }
  ]
}
```

**GET** `/api/v1/audit/logs/{id}/` → single log entry

---

## Phase 2 — Shipping Foundation

### 2.1 — `shipping` app (providers + services only)

#### Tasks
- [ ] `python3 manage.py startapp shipping`
- [ ] Add `'shipping'` to `INSTALLED_APPS`
- [ ] Create `shipping/models.py` — `CourierProvider`, `CourierService` (bookings/manifests/tracking_syncs added in Phase 9)
- [ ] Create `shipping/serializers.py`
- [ ] Create `shipping/views.py` — `CourierProviderViewSet`, `CourierServiceViewSet`
- [ ] Create `shipping/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations shipping && python3 manage.py migrate`

#### Model: `CourierProvider`
```python
# db_table = 'courier_providers'
name = CharField(max_length=50, choices=[ROYAL_MAIL, DPD, UPS, DHL, TRANSGLOBAL])
api_type = CharField(max_length=30)           # e.g. REST, SOAP
api_url = CharField(max_length=200)
credential = ForeignKey('config.ApiCredential', SET_NULL, null=True, blank=True)
is_active = BooleanField(default=True)
config = JSONField(null=True, blank=True)     # provider-specific settings
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `CourierService`
```python
# db_table = 'courier_services'
provider = ForeignKey(CourierProvider, CASCADE, related_name='services')
service_code = CharField(max_length=50)       # e.g. "TRK24", "DPD_ND"
service_name = CharField(max_length=100)      # e.g. "Tracked 24", "DPD Next Day"
delivery_type = CharField(max_length=30)      # STANDARD / NEXT_DAY_9AM / etc.
max_weight_g = IntegerField(null=True, blank=True)
is_active = BooleanField(default=True)
```

#### Endpoints

**POST** `/api/v1/shipping/providers/`
```json
// Request
{
  "name": "ROYAL_MAIL",
  "api_type": "REST",
  "api_url": "https://api.royalmail.com/shipping/v3",
  "credential_id": 1,
  "config": { "account_number": "XXXXXX", "contract_number": "YYYYYY" }
}

// Response 201
{
  "id": 1,
  "name": "ROYAL_MAIL",
  "api_type": "REST",
  "api_url": "https://api.royalmail.com/shipping/v3",
  "credential_id": 1,
  "is_active": true,
  "config": { "account_number": "XXXXXX", "contract_number": "YYYYYY" },
  "services": [],
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/shipping/providers/` → list all providers with nested services  
**GET** `/api/v1/shipping/providers/{id}/` → single provider  
**PATCH** `/api/v1/shipping/providers/{id}/` → update  
**DELETE** `/api/v1/shipping/providers/{id}/` → `204 No Content`

**POST** `/api/v1/shipping/services/`
```json
// Request
{
  "provider_id": 1,
  "service_code": "TRK24",
  "service_name": "Tracked 24",
  "delivery_type": "STANDARD",
  "max_weight_g": 2000
}

// Response 201
{
  "id": 1,
  "provider_id": 1,
  "provider_name": "ROYAL_MAIL",
  "service_code": "TRK24",
  "service_name": "Tracked 24",
  "delivery_type": "STANDARD",
  "max_weight_g": 2000,
  "is_active": true
}
```

**GET** `/api/v1/shipping/services/?provider_id=1` → filter by provider  
**PATCH** `/api/v1/shipping/services/{id}/` → update  
**DELETE** `/api/v1/shipping/services/{id}/` → `204 No Content`

---

## Phase 3 — Migrate Existing Tables

### 3.1 — `locations` table (`products` app migration)

#### Tasks
- [ ] Edit `products/models.py` — add 3 fields to `Location` model
- [ ] `python3 manage.py makemigrations products`
- [ ] `python3 manage.py migrate`

#### Fields to add to `Location`
```python
zone = ForeignKey('warehouse.WarehouseZone', SET_NULL, null=True, blank=True, related_name='locations')
bin_type = CharField(max_length=20, default='PICKING',
                     choices=[PICKING, BACKSTOCK, RESTRICTED, RETURNS, DISPATCH])
sort_order = IntegerField(default=0)
```

#### Updated Location response (existing `/api/v1/locations/` endpoints)
```json
// GET /api/v1/locations/{id}/
{
  "id": "LOC001",
  "name": "Aisle A Shelf 1",
  "description": "Ground floor main aisle",
  "zone_id": 1,
  "zone_name": "Main Picking Floor",
  "bin_type": "PICKING",
  "sort_order": 10,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-05-03T10:00:00Z"
}
```

#### PATCH `/api/v1/locations/{id}/` to assign zone
```json
// Request
{
  "zone_id": 1,
  "bin_type": "PICKING",
  "sort_order": 10
}
// Response 200 — updated location
```

---

### 3.2 — `orders` table (`orders` app migration)

#### Tasks
- [ ] Edit `orders/models.py` — add 6 new fields to `Order` model
- [ ] Add `DELIVERY_TYPE_CHOICES`, `PACKAGING_TYPE_CHOICES` constants
- [ ] `python3 manage.py makemigrations orders`
- [ ] `python3 manage.py migrate`

#### Fields to add to `Order`
```python
# NOTE: batch FK added after order_batches model created in Phase 4
batch = ForeignKey('orders.OrderBatch', SET_NULL, null=True, blank=True, related_name='order_set', db_index=True)
delivery_type = CharField(max_length=30, null=True, blank=True,
                          choices=[STANDARD, NEXT_DAY_9AM, NEXT_DAY_12PM, NEXT_DAY_1PM, SATURDAY, INTERNATIONAL])
priority = IntegerField(default=3)           # 1=Highest, 4=Lowest
packaging_type = CharField(max_length=30, null=True, blank=True,
                            choices=[PARCEL, EXPRESSPAK, WHOLESALE_PARCEL, LETTER, CUSTOM])
courier_provider = ForeignKey('shipping.CourierProvider', SET_NULL, null=True, blank=True)
courier_service = ForeignKey('shipping.CourierService', SET_NULL, null=True, blank=True)
# Meta indexes to add:
# Index(fields=['batch']),   named idx_orders_batch_id
# Index(fields=['priority', 'order_date']),   named idx_orders_priority
```

#### Migration note
The `batch` FK creates a circular dependency (`Order` → `OrderBatch` → `Order` via courier). Use a string reference `'orders.OrderBatch'` and run migrations in two steps:
1. Add `delivery_type`, `priority`, `packaging_type`, `courier_provider`, `courier_service` now
2. Add `batch` FK after `OrderBatch` model created in Phase 4

#### Updated Order response (existing `/api/v1/orders/` endpoints — new fields appended)
```json
// GET /api/v1/orders/{id}/
{
  "id": 1,
  "order_number": "ORD-20260503-0001",
  "order_status": "PENDING",
  "delivery_type": "STANDARD",
  "priority": 3,
  "packaging_type": "PARCEL",
  "courier_provider_id": 1,
  "courier_provider_name": "ROYAL_MAIL",
  "courier_service_id": 1,
  "courier_service_name": "Tracked 24",
  "batch_id": null,
  "... all existing fields ..."
}
```

---

### 3.3 — `order_items` table (`orders` app migration)

#### Tasks
- [ ] Edit `orders/models.py` — add 2 fields to `OrderItem` model
- [ ] Include in the same migration as 3.2 or run separately

#### Fields to add to `OrderItem`
```python
quantity_processed = IntegerField(default=0)
processing_status = CharField(max_length=20, default='PENDING',
                               choices=[PENDING, IN_PROGRESS, PICKED, EXCEPTION])
```

#### Updated OrderItem response (existing endpoints — new fields appended)
```json
{
  "id": 1,
  "order_id": 1,
  "sku": "109LT-BLK-001",
  "product_name": "109LT Black Roll",
  "quantity": 5,
  "quantity_ordered": 5,
  "quantity_processed": 0,
  "processing_status": "PENDING",
  "unit_price": "12.50",
  "line_total": "62.50",
  "... all existing fields ..."
}
```

---

### 3.4 — `stock` table (`stock` app migration)

#### Tasks
- [ ] Edit `stock/models.py` — add 1 field to `StockItem` model
- [ ] `python3 manage.py makemigrations stock && python3 manage.py migrate`

#### Field to add to `StockItem`
```python
last_batch_number = CharField(max_length=50, null=True, blank=True)
```

#### Updated StockItem response (existing endpoints — new field appended)
```json
{
  "sku": "109LT-BLK-001",
  "last_batch_number": "BATCH-20260503-001",
  "... all existing fields ..."
}
```

---

### 3.5 — `accounts_usertype` and `accounts_profile` (`accounts` app migration)

#### Tasks
- [ ] Edit `accounts/models.py` — add fields to both models
- [ ] `python3 manage.py makemigrations accounts && python3 manage.py migrate`

#### Fields to add to `UserType`
```python
permissions = JSONField(null=True, blank=True)
# Example value: {"orders": ["view","create","edit"], "stock": ["view"], "purchasing": ["view","create"]}
```

#### Fields to add to `Profile`
```python
notification_preferences = JSONField(null=True, blank=True)
# Example value: {"low_stock": true, "order_exception": true, "courier_failure": true}
last_login_ip = CharField(max_length=45, null=True, blank=True)
```

#### Updated UserType response
```json
{
  "id": 1,
  "name": "Warehouse Staff",
  "description": "Picks and packs orders",
  "permissions": {
    "orders": ["view", "edit"],
    "stock": ["view"],
    "mobile": ["view", "create"]
  }
}
```

#### Updated Profile response
```json
{
  "id": 1,
  "user_id": 5,
  "username": "john.smith",
  "usertype": { "id": 1, "name": "Warehouse Staff" },
  "notification_preferences": {
    "low_stock": true,
    "order_exception": true,
    "courier_failure": false,
    "sync_failure": true,
    "po_delivery": false
  },
  "last_login_ip": "192.168.1.22"
}
```

---

## Phase 4 — Orders App New Models

### 4.1 — `OrderBatch`

#### Tasks
- [ ] Add `OrderBatch` model to `orders/models.py`
- [ ] Add `BatchOrder` (M2M junction) model to `orders/models.py`
- [ ] Create migration, run it
- [ ] Add `batch` FK to `Order` model (second migration step from Phase 3.2)
- [ ] Create serializers, views, register URLs in `orders/urls.py`

#### Model: `OrderBatch`
```python
# db_table = 'order_batches'
batch_ref = CharField(max_length=50, unique=True)   # BATCH-YYYYMMDD-NNN auto-generated
status = CharField(max_length=20, default='PENDING',
                   choices=[PENDING, PROCESSING, DISPATCHED, COMPLETE])
priority = IntegerField(default=3)
courier_provider = ForeignKey('shipping.CourierProvider', SET_NULL, null=True, blank=True)
created_by = ForeignKey(User, SET_NULL, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
processed_at = DateTimeField(null=True, blank=True)
dispatched_at = DateTimeField(null=True, blank=True)
```

#### Model: `BatchOrder`
```python
# db_table = 'batch_orders'
batch = ForeignKey(OrderBatch, CASCADE, related_name='batch_orders')
order = ForeignKey(Order, CASCADE, related_name='batch_memberships')
# UniqueConstraint(fields=['batch', 'order'])
```

#### Endpoints

**POST** `/api/v1/orders/batches/`
```json
// Request
{
  "priority": 1,
  "courier_provider_id": 1,
  "order_ids": [101, 102, 103, 104]
}

// Response 201
{
  "id": 1,
  "batch_ref": "BATCH-20260503-001",
  "status": "PENDING",
  "priority": 1,
  "courier_provider_id": 1,
  "courier_provider_name": "ROYAL_MAIL",
  "order_count": 4,
  "orders": [101, 102, 103, 104],
  "created_by": "admin",
  "created_at": "2026-05-03T09:00:00Z",
  "processed_at": null,
  "dispatched_at": null
}
```

**GET** `/api/v1/orders/batches/`
```json
// Supports filters: ?status=PENDING&priority=1
// Response 200
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "batch_ref": "BATCH-20260503-001",
      "status": "PENDING",
      "priority": 1,
      "order_count": 4,
      "created_at": "2026-05-03T09:00:00Z"
    }
  ]
}
```

**GET** `/api/v1/orders/batches/{id}/`
```json
{
  "id": 1,
  "batch_ref": "BATCH-20260503-001",
  "status": "PENDING",
  "priority": 1,
  "courier_provider_id": 1,
  "order_count": 4,
  "orders": [
    { "id": 101, "order_number": "ORD-20260503-0001", "customer_name": "Jane Doe", "priority": 1 },
    { "id": 102, "order_number": "ORD-20260503-0002", "customer_name": "Bob Smith", "priority": 1 }
  ]
}
```

**POST** `/api/v1/orders/batches/{id}/add-orders/` (custom action)
```json
// Request
{ "order_ids": [105, 106] }
// Response 200
{ "batch_ref": "BATCH-20260503-001", "orders_added": 2, "order_count": 6 }
```

**POST** `/api/v1/orders/batches/{id}/update-status/` (custom action)
```json
// Request
{ "status": "PROCESSING" }
// Response 200
{ "id": 1, "batch_ref": "BATCH-20260503-001", "status": "PROCESSING", "processed_at": "2026-05-03T09:30:00Z" }
```

---

### 4.2 — `OrderException`

#### Tasks
- [ ] Add `OrderException` model to `orders/models.py`
- [ ] Create migration, run it
- [ ] Create serializers, views, register URLs

#### Model: `OrderException`
```python
# db_table = 'order_exceptions'
order = ForeignKey(Order, CASCADE, related_name='exceptions')
exception_type = CharField(max_length=50,
    choices=[VALIDATION_FAILED, COURIER_ERROR, SYNC_FAILED, ITEM_NOT_FOUND,
             DAMAGED, WRONG_LOCATION, QTY_DISCREPANCY, OTHER])
error_detail = TextField()
reported_by = ForeignKey(User, SET_NULL, null=True, blank=True, related_name='exceptions_reported')
resolved_by = ForeignKey(User, SET_NULL, null=True, blank=True, related_name='exceptions_resolved')
resolved_at = DateTimeField(null=True, blank=True)
status = CharField(max_length=20, default='OPEN', choices=[OPEN, RESOLVED, IGNORED])
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/orders/exceptions/`
```json
// Request
{
  "order_id": 101,
  "exception_type": "QTY_DISCREPANCY",
  "error_detail": "Picked 3 units but order requires 5. Only 3 available in LOC002."
}

// Response 201
{
  "id": 1,
  "order_id": 101,
  "order_number": "ORD-20260503-0001",
  "exception_type": "QTY_DISCREPANCY",
  "error_detail": "Picked 3 units but order requires 5. Only 3 available in LOC002.",
  "status": "OPEN",
  "reported_by": "warehouse_user",
  "resolved_by": null,
  "resolved_at": null,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/orders/exceptions/` — supports `?status=OPEN&order_id=101`  
**GET** `/api/v1/orders/exceptions/{id}/`  

**POST** `/api/v1/orders/exceptions/{id}/resolve/` (custom action)
```json
// Request
{ "resolution_notes": "Restocked from backstock location LOC015" }
// Response 200
{ "id": 1, "status": "RESOLVED", "resolved_by": "admin", "resolved_at": "2026-05-03T11:00:00Z" }
```

---

### 4.3 — `OrderNote`

#### Tasks
- [ ] Add `OrderNote` model to `orders/models.py`
- [ ] Create migration, run it
- [ ] Create serializers, views, register URLs

#### Model: `OrderNote`
```python
# db_table = 'order_notes'
order = ForeignKey(Order, CASCADE, related_name='notes')
note_type = CharField(max_length=20, choices=[INTERNAL, CUSTOMER, SYSTEM])
text = TextField()
created_by = ForeignKey(User, SET_NULL, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/orders/{order_id}/notes/`
```json
// Request
{
  "note_type": "INTERNAL",
  "text": "Customer called — prefers delivery after 2pm"
}

// Response 201
{
  "id": 1,
  "order_id": 101,
  "note_type": "INTERNAL",
  "text": "Customer called — prefers delivery after 2pm",
  "created_by": "admin",
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/orders/{order_id}/notes/`
```json
{
  "count": 2,
  "results": [
    { "id": 1, "note_type": "INTERNAL", "text": "...", "created_by": "admin", "created_at": "..." },
    { "id": 2, "note_type": "SYSTEM", "text": "Order batch assigned: BATCH-20260503-001", "created_by": null, "created_at": "..." }
  ]
}
```

---

## Phase 5 — Stock App New Models

### 5.1 — `StockBatch`

#### Tasks
- [ ] Add `StockBatch` model to `stock/models.py`
- [ ] `python3 manage.py makemigrations stock && python3 manage.py migrate`
- [ ] Create serializers, views, register URLs

#### Model: `StockBatch`
```python
# db_table = 'stock_batches'
batch_number = CharField(max_length=50, unique=True)    # BATCH-YYYYMMDD-NNN auto-generated
stock_item = ForeignKey(StockItem, CASCADE, to_field='sku', related_name='batches')
purchase_order = ForeignKey('purchasing.PurchaseOrder', SET_NULL, null=True, blank=True)
supplier = ForeignKey('purchasing.Supplier', SET_NULL, null=True, blank=True)
quantity = IntegerField()
received_date = DateTimeField()
received_by = ForeignKey(User, SET_NULL, null=True, blank=True)
expiry_date = DateTimeField(null=True, blank=True)
location = ForeignKey('products.Location', SET_NULL, null=True, blank=True)
notes = TextField(null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/stock/batches/`
```json
// Request
{
  "stock_sku": "109LT-BLK-001",
  "purchase_order_id": 5,
  "supplier_id": 2,
  "quantity": 100,
  "received_date": "2026-05-03T09:00:00Z",
  "location_id": "LOC001",
  "notes": "Received with PO-20260430-001"
}

// Response 201
{
  "id": 1,
  "batch_number": "BATCH-20260503-001",
  "stock_sku": "109LT-BLK-001",
  "purchase_order_id": 5,
  "purchase_order_ref": "PO-20260430-001",
  "supplier_id": 2,
  "supplier_name": "Acme Supplies Ltd",
  "quantity": 100,
  "received_date": "2026-05-03T09:00:00Z",
  "location_id": "LOC001",
  "notes": "Received with PO-20260430-001",
  "created_at": "2026-05-03T09:05:00Z"
}
```

**GET** `/api/v1/stock/batches/?stock_sku=109LT-BLK-001`
**GET** `/api/v1/stock/batches/{id}/`

---

### 5.2 — `Stocktake` and `StocktakeItem`

#### Tasks
- [ ] Add `Stocktake` and `StocktakeItem` models to `stock/models.py`
- [ ] Create migration, run it
- [ ] Create serializers, views, register URLs

#### Model: `Stocktake`
```python
# db_table = 'stocktakes'
stocktake_ref = CharField(max_length=50, unique=True)    # ST-YYYYMMDD-NNN auto-generated
location = ForeignKey('products.Location', SET_NULL, null=True, blank=True)
status = CharField(max_length=20, default='IN_PROGRESS', choices=[IN_PROGRESS, COMPLETED, CANCELLED])
started_by = ForeignKey(User, SET_NULL, null=True, blank=True)
started_at = DateTimeField(auto_now_add=True)
completed_at = DateTimeField(null=True, blank=True)
variance_count = IntegerField(default=0)
notes = TextField(null=True, blank=True)
```

#### Model: `StocktakeItem`
```python
# db_table = 'stocktake_items'
stocktake = ForeignKey(Stocktake, CASCADE, related_name='items')
stock_item = ForeignKey(StockItem, CASCADE, to_field='sku', related_name='stocktake_items')
expected_qty = IntegerField()
counted_qty = IntegerField()
variance = IntegerField()         # counted_qty - expected_qty
adjusted = BooleanField(default=False)
adjusted_at = DateTimeField(null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/stock/stocktakes/`
```json
// Request
{
  "location_id": "LOC001",
  "notes": "Monthly stocktake — Main Picking Floor"
}

// Response 201
{
  "id": 1,
  "stocktake_ref": "ST-20260503-001",
  "location_id": "LOC001",
  "location_name": "Aisle A Shelf 1",
  "status": "IN_PROGRESS",
  "started_by": "admin",
  "started_at": "2026-05-03T09:00:00Z",
  "variance_count": 0,
  "items": []
}
```

**POST** `/api/v1/stock/stocktakes/{id}/count/` (add item counts)
```json
// Request
{
  "items": [
    { "stock_sku": "109LT-BLK-001", "counted_qty": 48 },
    { "stock_sku": "109LT-WHT-002", "counted_qty": 23 }
  ]
}

// Response 200
{
  "stocktake_id": 1,
  "items_counted": 2,
  "variances": [
    { "stock_sku": "109LT-BLK-001", "expected_qty": 50, "counted_qty": 48, "variance": -2 },
    { "stock_sku": "109LT-WHT-002", "expected_qty": 23, "counted_qty": 23, "variance": 0 }
  ],
  "variance_count": 1
}
```

**POST** `/api/v1/stock/stocktakes/{id}/complete/`
```json
// Request — no body needed
// Response 200
{
  "id": 1,
  "stocktake_ref": "ST-20260503-001",
  "status": "COMPLETED",
  "completed_at": "2026-05-03T11:00:00Z",
  "variance_count": 1
}
```

**POST** `/api/v1/stock/stocktakes/{id}/apply-adjustments/` (creates StockMovements for variances)
```json
// Request
{ "adjust_all": true }
// or
{ "item_ids": [1, 3] }

// Response 200
{
  "adjustments_applied": 1,
  "stock_movements_created": 1
}
```

**GET** `/api/v1/stock/stocktakes/`  
**GET** `/api/v1/stock/stocktakes/{id}/`

---

## Phase 6 — Purchasing App

### 6.1 — `purchasing` app

#### Tasks
- [ ] `python3 manage.py startapp purchasing`
- [ ] Add `'purchasing'` to `INSTALLED_APPS`
- [ ] Create `purchasing/models.py` — `Supplier`, `PurchaseOrder`, `POItem`
- [ ] Create `purchasing/serializers.py`
- [ ] Create `purchasing/views.py` — viewsets for all 3 models
- [ ] Create `purchasing/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations purchasing && python3 manage.py migrate`

#### Model: `Supplier`
```python
# db_table = 'suppliers'
name = CharField(max_length=200)
contact_name = CharField(max_length=100, null=True, blank=True)
email = EmailField(null=True, blank=True)
phone = CharField(max_length=20, null=True, blank=True)
address = TextField(null=True, blank=True)
lead_time_days = IntegerField(default=7)
payment_terms = CharField(max_length=100, null=True, blank=True)
is_active = BooleanField(default=True)
notes = TextField(null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `PurchaseOrder`
```python
# db_table = 'purchase_orders'
po_reference = CharField(max_length=50, unique=True)    # PO-YYYYMMDD-NNN auto-generated
supplier = ForeignKey(Supplier, PROTECT, related_name='purchase_orders')
status = CharField(max_length=20, default='PENDING',
                   choices=[PENDING, OPEN, PARTIAL, DELIVERED, CANCELLED])
location = ForeignKey('products.Location', SET_NULL, null=True, blank=True)
order_date = DateTimeField(auto_now_add=True)
expected_delivery = DateTimeField(null=True, blank=True)
total_value = DecimalField(max_digits=12, decimal_places=2, default=0.00)
notes = TextField(null=True, blank=True)
created_by = ForeignKey(User, SET_NULL, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `POItem`
```python
# db_table = 'po_items'
purchase_order = ForeignKey(PurchaseOrder, CASCADE, related_name='items')
product = ForeignKey('products.Product', PROTECT, to_field='vs_child_id')
stock_item = ForeignKey('stock.StockItem', SET_NULL, null=True, blank=True, to_field='sku')
quantity_ordered = IntegerField()
quantity_delivered = IntegerField(default=0)
unit_cost = DecimalField(max_digits=10, decimal_places=2)
line_total = DecimalField(max_digits=12, decimal_places=2)
notes = TextField(null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/purchasing/suppliers/`
```json
// Request
{
  "name": "Acme Supplies Ltd",
  "contact_name": "Jane Smith",
  "email": "jane@acmesupplies.com",
  "phone": "01234 567890",
  "lead_time_days": 5,
  "payment_terms": "30 days net"
}

// Response 201
{
  "id": 1,
  "name": "Acme Supplies Ltd",
  "contact_name": "Jane Smith",
  "email": "jane@acmesupplies.com",
  "phone": "01234 567890",
  "lead_time_days": 5,
  "payment_terms": "30 days net",
  "is_active": true,
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/purchasing/suppliers/`  
**GET** `/api/v1/purchasing/suppliers/{id}/`  
**PATCH** `/api/v1/purchasing/suppliers/{id}/`  

**POST** `/api/v1/purchasing/purchase-orders/`
```json
// Request
{
  "supplier_id": 1,
  "location_id": "LOC001",
  "expected_delivery": "2026-05-10T09:00:00Z",
  "notes": "Urgent restock for 109LT",
  "items": [
    {
      "product_id": 12345,
      "stock_sku": "109LT-BLK-001",
      "quantity_ordered": 200,
      "unit_cost": "8.50"
    },
    {
      "product_id": 12346,
      "stock_sku": "109LT-WHT-002",
      "quantity_ordered": 100,
      "unit_cost": "8.50"
    }
  ]
}

// Response 201
{
  "id": 5,
  "po_reference": "PO-20260503-001",
  "supplier": { "id": 1, "name": "Acme Supplies Ltd" },
  "status": "PENDING",
  "location_id": "LOC001",
  "order_date": "2026-05-03T10:00:00Z",
  "expected_delivery": "2026-05-10T09:00:00Z",
  "total_value": "2550.00",
  "items": [
    {
      "id": 1,
      "product_id": 12345,
      "stock_sku": "109LT-BLK-001",
      "quantity_ordered": 200,
      "quantity_delivered": 0,
      "unit_cost": "8.50",
      "line_total": "1700.00"
    },
    {
      "id": 2,
      "product_id": 12346,
      "stock_sku": "109LT-WHT-002",
      "quantity_ordered": 100,
      "quantity_delivered": 0,
      "unit_cost": "8.50",
      "line_total": "850.00"
    }
  ]
}
```

**GET** `/api/v1/purchasing/purchase-orders/?status=OPEN`  
**GET** `/api/v1/purchasing/purchase-orders/{id}/`  

**POST** `/api/v1/purchasing/purchase-orders/{id}/receive/` (custom action — mark items as delivered)
```json
// Request
{
  "items": [
    { "po_item_id": 1, "quantity_delivered": 200 },
    { "po_item_id": 2, "quantity_delivered": 80 }
  ]
}

// Response 200
{
  "po_reference": "PO-20260503-001",
  "status": "PARTIAL",
  "stock_movements_created": 2,
  "items": [
    { "po_item_id": 1, "quantity_ordered": 200, "quantity_delivered": 200, "fully_received": true },
    { "po_item_id": 2, "quantity_ordered": 100, "quantity_delivered": 80, "fully_received": false }
  ]
}
```

---

## Phase 7 — Channels App

### 7.1 — `channels` app

#### Tasks
- [ ] `python3 manage.py startapp channels`
- [ ] Add `'channels'` to `INSTALLED_APPS`

> **Note:** Django has a built-in `channels` package (for WebSockets). If installed, name this app `sales_channels` or use `app_label = 'sales_channels'` in Meta. Confirm first.

- [ ] Create `channels/models.py` (or `sales_channels/models.py`) — `Channel`, `ChannelMapping`, `IngestionLog`
- [ ] Create serializers, views, urls
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations channels && python3 manage.py migrate`

#### Model: `Channel`
```python
# db_table = 'channels'
name = CharField(max_length=50)
platform_type = CharField(max_length=20, choices=[WEBSITE, AMAZON, EBAY, ETSY])
api_url = CharField(max_length=200, null=True, blank=True)
credential = ForeignKey('config.ApiCredential', SET_NULL, null=True, blank=True)
poll_interval_mins = IntegerField(default=15)
webhook_enabled = BooleanField(default=False)
is_active = BooleanField(default=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `ChannelMapping`
```python
# db_table = 'channel_mappings'
product = ForeignKey('products.Product', CASCADE, to_field='vs_child_id')
channel = ForeignKey(Channel, CASCADE, related_name='mappings')
channel_sku = CharField(max_length=100)
channel_listing_id = CharField(max_length=100, null=True, blank=True)
is_active = BooleanField(default=True)
created_at = DateTimeField(auto_now_add=True)
# UniqueConstraint(fields=['channel', 'channel_sku'])
```

#### Model: `IngestionLog`
```python
# db_table = 'ingestion_logs'
channel = ForeignKey(Channel, CASCADE, related_name='ingestion_logs')
poll_timestamp = DateTimeField(auto_now_add=True)
orders_imported = IntegerField(default=0)
orders_skipped = IntegerField(default=0)
errors = IntegerField(default=0)
error_details = TextField(null=True, blank=True)
status = CharField(max_length=20, choices=[SUCCESS, PARTIAL, FAILED])
duration_seconds = DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/channels/`
```json
// Request
{
  "name": "Visualsoft Website",
  "platform_type": "WEBSITE",
  "api_url": "https://api.visualsoft.com/orders",
  "credential_id": 2,
  "poll_interval_mins": 10
}

// Response 201
{
  "id": 1,
  "name": "Visualsoft Website",
  "platform_type": "WEBSITE",
  "api_url": "https://api.visualsoft.com/orders",
  "credential_id": 2,
  "poll_interval_mins": 10,
  "webhook_enabled": false,
  "is_active": true
}
```

**GET** `/api/v1/channels/`  
**GET** `/api/v1/channels/{id}/`  
**PATCH** `/api/v1/channels/{id}/`  

**POST** `/api/v1/channels/mappings/`
```json
// Request
{
  "product_id": 12345,
  "channel_id": 1,
  "channel_sku": "VS-109LT-BLK",
  "channel_listing_id": "LISTING-001"
}

// Response 201
{
  "id": 1,
  "product_id": 12345,
  "channel_id": 1,
  "channel_name": "Visualsoft Website",
  "channel_sku": "VS-109LT-BLK",
  "channel_listing_id": "LISTING-001",
  "is_active": true
}
```

**GET** `/api/v1/channels/ingestion-logs/?channel_id=1`
```json
{
  "count": 144,
  "results": [
    {
      "id": 1,
      "channel_id": 1,
      "channel_name": "Visualsoft Website",
      "poll_timestamp": "2026-05-03T10:00:00Z",
      "orders_imported": 12,
      "orders_skipped": 1,
      "errors": 0,
      "status": "SUCCESS",
      "duration_seconds": "2.34"
    }
  ]
}
```

---

### 7.2 — `ChannelStockSyncLog` model (add to `channels` app)

#### Tasks
- [ ] Add `ChannelStockSyncLog` model to `channels/models.py` (or `sales_channels/models.py`)
- [ ] Add `ChannelStockSyncLogViewSet` (read-only list) to views
- [ ] Add `POST /api/v1/stock/sync-channels/` view to `stock/views.py`
- [ ] Run `python3 manage.py makemigrations channels && python3 manage.py migrate`

#### Model: `ChannelStockSyncLog`
```python
# db_table = 'channel_stock_sync_log'
channel = ForeignKey(Channel, CASCADE, related_name='stock_sync_logs')
stock_item = ForeignKey('stock.StockItem', CASCADE, to_field='sku', related_name='channel_syncs')
synced_qty = IntegerField()
sync_status = CharField(max_length=20, choices=[('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')])
error_message = TextField(null=True, blank=True)
synced_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/stock/sync-channels/` (triggers stock quantity push to all active channels)
```json
// Request
{
  "stock_skus": ["109LT-BLK-001", "109LT-WHT-002"],
  "channel_ids": [1, 2]
}
// or omit both fields to sync ALL active stock to ALL active channels

// Response 200
{
  "synced": 2,
  "skipped": 0,
  "failed": 0,
  "details": [
    { "sku": "109LT-BLK-001", "channel_id": 1, "synced_qty": 48, "status": "SUCCESS" },
    { "sku": "109LT-BLK-001", "channel_id": 2, "synced_qty": 48, "status": "SUCCESS" },
    { "sku": "109LT-WHT-002", "channel_id": 1, "synced_qty": 23, "status": "SUCCESS" },
    { "sku": "109LT-WHT-002", "channel_id": 2, "synced_qty": 23, "status": "SUCCESS" }
  ]
}
```

**GET** `/api/v1/channels/stock-sync-logs/?channel_id=1&sync_status=FAILED`
```json
{
  "count": 3,
  "results": [
    {
      "id": 5,
      "channel_id": 1,
      "channel_name": "Visualsoft Website",
      "stock_sku": "109LT-BLK-001",
      "synced_qty": 0,
      "sync_status": "FAILED",
      "error_message": "Channel API timeout after 30s",
      "synced_at": "2026-05-03T10:15:00Z"
    }
  ]
}
```

---

## Phase 8 — Purchasing POItems

### 8.1 — Migrate `po_items` (if deferred)

> If `POItem` was created in Phase 6 without the `stock_item` FK (to avoid circular dep), add that FK now via a new migration.  
> If it was already included in Phase 6, skip this phase.

---

## Phase 9 — Shipping Completion

### 9.1 — `CourierBooking`, `Manifest`, `TrackingSync`

#### Tasks
- [ ] Add 3 remaining models to `shipping/models.py`
- [ ] `python3 manage.py makemigrations shipping && python3 manage.py migrate`
- [ ] Add viewsets and URLs for all 3

#### Model: `CourierBooking`
```python
# db_table = 'courier_bookings'
order = ForeignKey('orders.Order', CASCADE, related_name='courier_bookings')
provider = ForeignKey(CourierProvider, CASCADE, related_name='bookings')
service = ForeignKey(CourierService, SET_NULL, null=True, blank=True)
tracking_number = CharField(max_length=100)
label_data = TextField(null=True, blank=True)         # base64 PDF or ZPL string
label_format = CharField(max_length=10, choices=[PDF, ZPL])
booking_status = CharField(max_length=20, default='BOOKED',
                            choices=[BOOKED, LABEL_GENERATED, MANIFESTED, FAILED])
booked_at = DateTimeField(auto_now_add=True)
error_message = TextField(null=True, blank=True)
```

#### Model: `Manifest`
```python
# db_table = 'manifests'
provider = ForeignKey(CourierProvider, CASCADE, related_name='manifests')
manifest_ref = CharField(max_length=50)
manifest_date = DateField()
booking_count = IntegerField()
pdf_data = TextField(null=True, blank=True)
filed_at = DateTimeField(auto_now_add=True)
filed_by = ForeignKey(User, SET_NULL, null=True, blank=True)
```

#### Model: `TrackingSync`
```python
# db_table = 'tracking_syncs'
order = ForeignKey('orders.Order', CASCADE, related_name='tracking_syncs')
channel = ForeignKey('channels.Channel', SET_NULL, null=True, blank=True)
tracking_number = CharField(max_length=100)
sync_status = CharField(max_length=20, default='PENDING', choices=[PENDING, SENT, FAILED])
attempts = IntegerField(default=0)
last_attempt_at = DateTimeField(null=True, blank=True)
synced_at = DateTimeField(null=True, blank=True)
error_message = TextField(null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/shipping/bookings/`
```json
// Request
{
  "order_id": 101,
  "provider_id": 1,
  "service_id": 1,
  "label_format": "PDF"
}

// Response 201
{
  "id": 1,
  "order_id": 101,
  "order_number": "ORD-20260503-0001",
  "provider_name": "ROYAL_MAIL",
  "service_name": "Tracked 24",
  "tracking_number": "JD000000001GB",
  "label_format": "PDF",
  "label_data": "base64_encoded_pdf_string...",
  "booking_status": "LABEL_GENERATED",
  "booked_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/shipping/bookings/?order_id=101`  
**GET** `/api/v1/shipping/bookings/{id}/`  

**POST** `/api/v1/shipping/manifests/`
```json
// Request
{
  "provider_id": 1,
  "manifest_date": "2026-05-03",
  "booking_ids": [1, 2, 3, 4, 5]
}

// Response 201
{
  "id": 1,
  "provider_name": "ROYAL_MAIL",
  "manifest_ref": "MANIFEST-20260503-001",
  "manifest_date": "2026-05-03",
  "booking_count": 5,
  "pdf_data": "base64_encoded_pdf_string...",
  "filed_at": "2026-05-03T17:00:00Z",
  "filed_by": "admin"
}
```

**GET** `/api/v1/shipping/tracking-syncs/?sync_status=FAILED`
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "order_id": 101,
      "order_number": "ORD-20260503-0001",
      "channel_id": 1,
      "channel_name": "Visualsoft Website",
      "tracking_number": "JD000000001GB",
      "sync_status": "FAILED",
      "attempts": 2,
      "last_attempt_at": "2026-05-03T10:15:00Z",
      "error_message": "Channel API timeout"
    }
  ]
}
```

**POST** `/api/v1/shipping/tracking-syncs/{id}/retry/` → `200 { "sync_status": "SENT", "synced_at": "..." }`

---

### 9.2 — `ShippingLabel` and `PrintJob` models (add to `shipping` app)

#### Tasks
- [ ] Add `ShippingLabel` and `PrintJob` models to `shipping/models.py`
- [ ] Add `ShippingLabelViewSet`, `PrintJobViewSet` to `shipping/views.py`
- [ ] Add label queue + print endpoints to `shipping/urls.py`
- [ ] Add reprint endpoint: `POST /api/v1/orders/{id}/label/reprint/` to `orders/urls.py`
- [ ] Run `python3 manage.py makemigrations shipping && python3 manage.py migrate`

#### Model: `ShippingLabel`
```python
# db_table = 'shipping_labels'
courier_booking = ForeignKey('CourierBooking', CASCADE, related_name='labels')
label_format = CharField(max_length=10, choices=[('PDF', 'PDF'), ('ZPL', 'ZPL')])
label_data = TextField()     # base64-encoded label content
generated_at = DateTimeField(auto_now_add=True)
```

#### Model: `PrintJob`
```python
# db_table = 'print_jobs'
label = ForeignKey(ShippingLabel, CASCADE, related_name='print_jobs')
printer_config = ForeignKey('config.PrintConfig', SET_NULL, null=True, blank=True,
                             related_name='print_jobs')
status = CharField(max_length=20, default='QUEUED',
                   choices=[('QUEUED', 'Queued'), ('PRINTING', 'Printing'),
                             ('DONE', 'Done'), ('FAILED', 'Failed')])
queued_at = DateTimeField(auto_now_add=True)
printed_at = DateTimeField(null=True, blank=True)
error_message = TextField(null=True, blank=True)
```

#### Endpoints

**GET** `/api/v1/labels/queue/`
```json
// Returns all QUEUED print jobs
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "label_id": 3,
      "order_number": "ORD-20260503-0001",
      "tracking_number": "JD000000001GB",
      "label_format": "ZPL",
      "printer_name": "Zebra ZD420 Label Printer",
      "status": "QUEUED",
      "queued_at": "2026-05-03T10:00:00Z"
    }
  ]
}
```

**POST** `/api/v1/labels/print/`
```json
// Request — send label(s) to printer
{
  "print_job_ids": [1, 2, 3],
  "printer_id": 1
}

// Response 200
{
  "sent_to_printer": 3,
  "failed": 0,
  "jobs": [
    { "print_job_id": 1, "status": "PRINTING" },
    { "print_job_id": 2, "status": "PRINTING" },
    { "print_job_id": 3, "status": "PRINTING" }
  ]
}
```

**POST** `/api/v1/orders/{id}/label/reprint/`
```json
// Request
{
  "printer_id": 1,
  "label_format": "ZPL"
}

// Response 201
{
  "order_id": 101,
  "order_number": "ORD-20260503-0001",
  "label_id": 4,
  "print_job_id": 6,
  "tracking_number": "JD000000001GB",
  "status": "QUEUED"
}
```

---

## Phase 10 — Rules Engine

### 10.1 — `rules` app

#### Tasks
- [ ] `python3 manage.py startapp rules`
- [ ] Add `'rules'` to `INSTALLED_APPS`
- [ ] Create `rules/models.py` — `Rule`, `RuleChangeLog`
- [ ] Create `rules/serializers.py`
- [ ] Create `rules/views.py` — `RuleViewSet`, `RuleChangeLogViewSet` (read-only)
- [ ] Create `rules/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations rules && python3 manage.py migrate`

#### Model: `Rule`
```python
# db_table = 'rules'
rule_type = CharField(max_length=30,
    choices=[DELIVERY_TYPE, PACKAGING, WEIGHT_COURIER, COURIER_SERVICE, PRIORITY, COURIER_TIMELINE])
name = CharField(max_length=100)
description = TextField(null=True, blank=True)
conditions = JSONField()
actions = JSONField()
priority = IntegerField(default=100)
is_active = BooleanField(default=True)
created_by = ForeignKey(User, SET_NULL, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```

#### Model: `RuleChangeLog`
```python
# db_table = 'rule_change_log'
rule = ForeignKey(Rule, CASCADE, related_name='change_log')
changed_by = ForeignKey(User, SET_NULL, null=True, blank=True)
before_state = JSONField()
after_state = JSONField()
change_reason = CharField(max_length=200, null=True, blank=True)
timestamp = DateTimeField(auto_now_add=True)
```

#### Endpoints

**POST** `/api/v1/rules/`
```json
// Request
{
  "rule_type": "DELIVERY_TYPE",
  "name": "Next Day 9AM — Priority 1 Orders",
  "description": "All P1 orders default to Next Day 9AM delivery",
  "priority": 10,
  "conditions": {
    "operator": "AND",
    "checks": [
      { "field": "order.priority", "op": "eq", "value": 1 }
    ]
  },
  "actions": {
    "set_delivery_type": "NEXT_DAY_9AM",
    "set_packaging_type": "EXPRESSPAK"
  }
}

// Response 201
{
  "id": 1,
  "rule_type": "DELIVERY_TYPE",
  "name": "Next Day 9AM — Priority 1 Orders",
  "priority": 10,
  "is_active": true,
  "conditions": { ... },
  "actions": { ... },
  "created_by": "admin",
  "created_at": "2026-05-03T10:00:00Z"
}
```

**GET** `/api/v1/rules/?rule_type=DELIVERY_TYPE&is_active=true`  
**GET** `/api/v1/rules/{id}/`  
**PATCH** `/api/v1/rules/{id}/`  
**DELETE** `/api/v1/rules/{id}/`  

**POST** `/api/v1/rules/evaluate/` (custom action — test a rule against an order)
```json
// Request
{
  "order_id": 101
}

// Response 200
{
  "order_id": 101,
  "rules_evaluated": 8,
  "applied": [
    { "rule_id": 1, "rule_name": "Next Day 9AM — Priority 1 Orders", "actions": { "set_delivery_type": "NEXT_DAY_9AM" } }
  ],
  "result": {
    "delivery_type": "NEXT_DAY_9AM",
    "packaging_type": "EXPRESSPAK",
    "priority": 1,
    "courier_provider_id": 1,
    "courier_service_id": 2
  }
}
```

**GET** `/api/v1/rules/{id}/change-log/`
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "changed_by": "admin",
      "before_state": { "is_active": true },
      "after_state": { "is_active": false },
      "change_reason": "Temporarily disabled for testing",
      "timestamp": "2026-05-03T11:00:00Z"
    }
  ]
}
```

---

## Phase 11 — Mobile / QR Processing

### 11.1 — `mobile` app

#### Tasks
- [ ] `python3 manage.py startapp mobile`
- [ ] Add `'mobile'` to `INSTALLED_APPS`
- [ ] Create `mobile/models.py` — `QRCode`, `ProcessingLog`
- [ ] Create `mobile/serializers.py`
- [ ] Create `mobile/views.py` — `QRCodeViewSet`, `ProcessingLogViewSet`
- [ ] Create `mobile/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations mobile && python3 manage.py migrate`

#### Model: `QRCode`
```python
# db_table = 'qr_codes'
order_item = ForeignKey('orders.OrderItem', CASCADE, related_name='qr_codes')
qr_data = JSONField()
# qr_data structure: { "order_number": "ORD-...", "sku": "...", "location_id": "LOC001", "qty_required": 5, "delivery_type": "STANDARD" }
generated_at = DateTimeField(auto_now_add=True)
```

#### Model: `ProcessingLog`
```python
# db_table = 'processing_logs'
order_item = ForeignKey('orders.OrderItem', CASCADE, related_name='processing_logs')
action = CharField(max_length=20, choices=[SCAN, INCREMENT, DECREMENT, CONFIRM, EXCEPTION])
quantity_change = IntegerField(null=True, blank=True)
performed_by = ForeignKey(User, SET_NULL, null=True, blank=True)
timestamp = DateTimeField(auto_now_add=True)
device_info = CharField(max_length=200, null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/mobile/qr-codes/generate/` (custom action — bulk generate for an order)
```json
// Request
{ "order_id": 101 }

// Response 201
{
  "order_id": 101,
  "order_number": "ORD-20260503-0001",
  "qr_codes_generated": 3,
  "qr_codes": [
    {
      "id": 1,
      "order_item_id": 5,
      "sku": "109LT-BLK-001",
      "qr_data": {
        "order_number": "ORD-20260503-0001",
        "sku": "109LT-BLK-001",
        "location_id": "LOC001",
        "qty_required": 5,
        "delivery_type": "STANDARD"
      },
      "qr_image_base64": "data:image/png;base64,iVBOR...",
      "generated_at": "2026-05-03T09:00:00Z"
    }
  ]
}
```

**POST** `/api/v1/mobile/scan/` (main mobile processing endpoint)
```json
// Request — sent when mobile device scans a QR code
{
  "order_item_id": 5,
  "action": "SCAN",
  "device_info": "iPad-Warehouse-01"
}

// Response 200
{
  "order_item_id": 5,
  "sku": "109LT-BLK-001",
  "order_number": "ORD-20260503-0001",
  "location_id": "LOC001",
  "qty_required": 5,
  "qty_processed": 0,
  "processing_status": "IN_PROGRESS",
  "action_logged": "SCAN"
}
```

**POST** `/api/v1/mobile/process/` (increment/decrement picked qty)
```json
// Request
{
  "order_item_id": 5,
  "action": "INCREMENT",
  "quantity_change": 1
}

// Response 200
{
  "order_item_id": 5,
  "sku": "109LT-BLK-001",
  "qty_required": 5,
  "qty_processed": 3,
  "processing_status": "IN_PROGRESS"
}
```

**POST** `/api/v1/mobile/confirm/`
```json
// Request
{ "order_item_id": 5 }

// Response 200 — marks item as PICKED
{
  "order_item_id": 5,
  "processing_status": "PICKED",
  "qty_processed": 5,
  "order_fully_picked": false,
  "remaining_items": 2
}
```

**GET** `/api/v1/mobile/processing-logs/?order_item_id=5`

---

## Phase 11.2 — Pick List Generation

### 11.2 — `PickList` and `PickListItem` models (add to `mobile` app)

#### Tasks
- [ ] Add `PickList` and `PickListItem` models to `mobile/models.py`
- [ ] Add `PickListViewSet` to `mobile/views.py`
- [ ] Register pick list endpoints in `mobile/urls.py`
- [ ] Register batch pick-list endpoints in `orders/urls.py`
- [ ] Run `python3 manage.py makemigrations mobile && python3 manage.py migrate`
- [ ] Install PDF generation lib if not already: `pip install weasyprint`

#### Model: `PickList`
```python
# db_table = 'pick_lists'
batch = ForeignKey('orders.OrderBatch', CASCADE, related_name='pick_lists')
generated_at = DateTimeField(auto_now_add=True)
generated_by = ForeignKey(User, SET_NULL, null=True, blank=True, related_name='pick_lists_generated')
pdf_data = TextField(null=True, blank=True)    # base64-encoded PDF
```

#### Model: `PickListItem`
```python
# db_table = 'pick_list_items'
pick_list = ForeignKey(PickList, CASCADE, related_name='items')
order_item = ForeignKey('orders.OrderItem', CASCADE, related_name='pick_list_items')
stock_item = ForeignKey('stock.StockItem', SET_NULL, null=True, blank=True, to_field='sku')
location = ForeignKey('products.Location', SET_NULL, null=True, blank=True)
sort_order = IntegerField(default=0)     # based on locations.sort_order for optimised picking route
is_confirmed = BooleanField(default=False)
confirmed_at = DateTimeField(null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/batches/{id}/pick-list/`
```json
// Request — generate pick list for a batch (no body needed)
// Response 201
{
  "id": 1,
  "batch_ref": "BATCH-20260503-001",
  "pick_list_id": 1,
  "generated_at": "2026-05-03T09:00:00Z",
  "generated_by": "admin",
  "total_items": 12,
  "items": [
    {
      "id": 1,
      "order_number": "ORD-20260503-0001",
      "order_item_id": 5,
      "sku": "109LT-BLK-001",
      "product_name": "109LT Black Roll",
      "location_id": "LOC001",
      "location_name": "Aisle A Shelf 1",
      "quantity": 5,
      "sort_order": 10,
      "is_confirmed": false
    }
  ]
}
```

**GET** `/api/v1/batches/{id}/pick-list/pdf/`
```json
// Response 200 — returns PDF as base64
{
  "pick_list_id": 1,
  "batch_ref": "BATCH-20260503-001",
  "pdf_data": "data:application/pdf;base64,JVBERi0xLjQ..."
}
```

**POST** `/api/v1/pick-lists/{id}/scan-confirm/`
```json
// Request — warehouse operative scans barcode to confirm item picked
{
  "order_item_id": 5,
  "sku": "109LT-BLK-001"
}

// Response 200
{
  "pick_list_item_id": 1,
  "sku": "109LT-BLK-001",
  "is_confirmed": true,
  "confirmed_at": "2026-05-03T09:15:00Z",
  "pick_list_complete": false,
  "remaining_items": 11
}
```

**GET** `/api/v1/batches/{id}/packing-lists/pdf/`
```json
// Response 200 — packing slip PDF for all orders in batch (one per order)
{
  "batch_ref": "BATCH-20260503-001",
  "order_count": 4,
  "pdf_data": "data:application/pdf;base64,JVBERi0xLjQ..."
}
```

---

## Phase 12 — Returns

### 12.1 — `returns` app

#### Tasks
- [ ] `python3 manage.py startapp returns`
- [ ] Add `'returns'` to `INSTALLED_APPS`
- [ ] Create `returns/models.py` — `Return`, `ReturnItem`
- [ ] Create `returns/serializers.py`
- [ ] Create `returns/views.py` — `ReturnViewSet`, `ReturnItemViewSet`
- [ ] Create `returns/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations returns && python3 manage.py migrate`

#### Model: `Return`
```python
# db_table = 'returns'
order = ForeignKey('orders.Order', CASCADE, related_name='returns')
rma_number = CharField(max_length=50, unique=True)    # RMA-YYYYMMDD-NNN auto-generated
status = CharField(max_length=20, default='REQUESTED',
                   choices=[REQUESTED, APPROVED, RECEIVED, RESTOCKED, REJECTED])
reason_code = CharField(max_length=50)
notes = TextField(null=True, blank=True)
created_by = ForeignKey(User, SET_NULL, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
received_at = DateTimeField(null=True, blank=True)
```

#### Model: `ReturnItem`
```python
# db_table = 'return_items'
return_request = ForeignKey(Return, CASCADE, related_name='items')
order_item = ForeignKey('orders.OrderItem', CASCADE, related_name='return_items')
quantity = IntegerField()
condition = CharField(max_length=20, choices=[GOOD, DAMAGED, DEFECTIVE])
restock = BooleanField(default=False)
restocked_at = DateTimeField(null=True, blank=True)
```

#### Endpoints

**POST** `/api/v1/returns/`
```json
// Request
{
  "order_id": 101,
  "reason_code": "WRONG_ITEM",
  "notes": "Customer received wrong colour",
  "items": [
    {
      "order_item_id": 5,
      "quantity": 2,
      "condition": "GOOD",
      "restock": true
    }
  ]
}

// Response 201
{
  "id": 1,
  "rma_number": "RMA-20260503-001",
  "order_id": 101,
  "order_number": "ORD-20260503-0001",
  "status": "REQUESTED",
  "reason_code": "WRONG_ITEM",
  "notes": "Customer received wrong colour",
  "created_by": "admin",
  "created_at": "2026-05-03T10:00:00Z",
  "items": [
    {
      "id": 1,
      "order_item_id": 5,
      "sku": "109LT-BLK-001",
      "quantity": 2,
      "condition": "GOOD",
      "restock": true,
      "restocked_at": null
    }
  ]
}
```

**GET** `/api/v1/returns/?status=REQUESTED`  
**GET** `/api/v1/returns/{id}/`  

**POST** `/api/v1/returns/{id}/approve/`
```json
// Response 200
{ "id": 1, "rma_number": "RMA-20260503-001", "status": "APPROVED" }
```

**POST** `/api/v1/returns/{id}/receive/`
```json
// Request — update condition on actual receipt
{
  "items": [
    { "return_item_id": 1, "condition": "DAMAGED" }
  ]
}
// Response 200
{ "id": 1, "status": "RECEIVED", "received_at": "2026-05-05T10:00:00Z" }
```

**POST** `/api/v1/returns/{id}/restock/` (creates StockMovement RETURNED for eligible items)
```json
// Response 200
{
  "id": 1,
  "status": "RESTOCKED",
  "items_restocked": 1,
  "items_written_off": 0,
  "stock_movements_created": 1
}
```

---

## Phase 13 — Notifications

### 13.1 — `notifications` app

#### Tasks
- [ ] `python3 manage.py startapp notifications`
- [ ] Add `'notifications'` to `INSTALLED_APPS`
- [ ] Create `notifications/models.py` — `Notification`
- [ ] Create `notifications/serializers.py`
- [ ] Create `notifications/views.py` — `NotificationViewSet`
- [ ] Create `notifications/urls.py`
- [ ] Register in `inventory_management/urls.py`
- [ ] `python3 manage.py makemigrations notifications && python3 manage.py migrate`

#### Model: `Notification`
```python
# db_table = 'notifications'
user = ForeignKey(User, CASCADE, related_name='notifications')
notification_type = CharField(max_length=30,
    choices=[LOW_STOCK, ORDER_EXCEPTION, COURIER_FAILURE, SYNC_FAILURE, PO_DELIVERY, SYSTEM])
title = CharField(max_length=200)
message = TextField()
is_read = BooleanField(default=False)
link_url = CharField(max_length=200, null=True, blank=True)
created_at = DateTimeField(auto_now_add=True)
```

#### Endpoints

**GET** `/api/v1/notifications/` (scoped to authenticated user)
```json
{
  "count": 5,
  "unread_count": 3,
  "results": [
    {
      "id": 1,
      "notification_type": "LOW_STOCK",
      "title": "Low stock alert: 109LT-BLK-001",
      "message": "Stock level (3) is below minimum threshold (10) for SKU 109LT-BLK-001.",
      "is_read": false,
      "link_url": "/stock/109LT-BLK-001/",
      "created_at": "2026-05-03T08:00:00Z"
    }
  ]
}
```

**POST** `/api/v1/notifications/{id}/mark-read/`
```json
// Response 200
{ "id": 1, "is_read": true }
```

**POST** `/api/v1/notifications/mark-all-read/`
```json
// Response 200
{ "marked_read": 3 }
```

**DELETE** `/api/v1/notifications/{id}/` → `204 No Content`

---

## Phase 14 — Courier Booking Rules Seed Data

### 14.1 — Seed CR01–CR15 courier routing rules

> Once the `rules` app is set up (Phase 10) and `shipping` courier services are seeded (Phase 2), run this management command to create the 15 predefined courier routing rules.

#### Tasks
- [ ] Create `rules/management/commands/seed_courier_rules.py`
- [ ] Run: `python3 manage.py seed_courier_rules`
- [ ] Verify all 15 rules created: `GET /api/v1/rules/?rule_type=COURIER_SERVICE`

#### Seed data — 15 rules (CR01–CR15)

| Rule | Courier | Service Code | Condition Summary |
|---|---|---|---|
| CR01 | Royal Mail | RM_TRACKED_48 | weight ≤ 3000g, UK, STANDARD |
| CR02 | DPD | DPD_PARCEL | weight > 3000g, UK, STANDARD |
| CR03 | Royal Mail | RM_SPECIAL_1PM | NEXT_DAY_1PM, weight ≤ 3000g |
| CR04 | DPD | DPD_NEXT_DAY_12 | NEXT_DAY_12PM (any weight) |
| CR05 | DPD | DPD_NEXT_DAY | NEXT_DAY_1PM, weight > 3000g |
| CR06 | Royal Mail | RM_SPECIAL_SAT | SATURDAY, weight ≤ 3000g |
| CR07 | DPD | DPD_SAT | SATURDAY, weight > 3000g |
| CR08 | DPD | DPD_PARCEL | product_type='Fleece', total_metres ≥ 6 |
| CR09 | Royal Mail | RM_TRACKED_24 | product_type='Sample' OR (weight ≤ 3000g AND items ≤ 2) |
| CR10 | DPD | DPD_PARCEL_PRIORITY | any product is trade_only_product=True |
| CR11 | DHL | DHL_EXPRESS_EU | shipping_country IN EU countries |
| CR12 | DHL | DHL_EXPRESS_INTL | shipping_country NOT IN UK/EU |
| CR13 | Royal Mail | RM_INTL_TRACKED | international, weight ≤ 2000g |
| CR14 | UPS | UPS_STANDARD | weight > 30000g, UK |
| CR15 | Transglobal | TG_ECONOMY | delivery_type='ECONOMY', courier_override='TRANSGLOBAL' |

#### Management command `seed_courier_rules.py`:
```python
from django.core.management.base import BaseCommand
from rules.models import Rule

EU_COUNTRIES = [
    'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
    'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
    'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
]

RULES = [
    {
        'name': 'CR01 — Royal Mail Tracked 48 (Standard UK ≤3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 10,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'eq', 'value': 'GB'},
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'STANDARD'},
                {'field': 'order.total_weight_g', 'op': 'lte', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'ROYAL_MAIL',
            'set_courier_service': 'RM_TRACKED_48',
        }
    },
    {
        'name': 'CR02 — DPD Parcel (Standard UK >3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 20,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'eq', 'value': 'GB'},
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'STANDARD'},
                {'field': 'order.total_weight_g', 'op': 'gt', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_PARCEL',
        }
    },
    {
        'name': 'CR03 — Royal Mail Special Delivery 1PM (Next Day 1PM ≤3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 30,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'NEXT_DAY_1PM'},
                {'field': 'order.total_weight_g', 'op': 'lte', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'ROYAL_MAIL',
            'set_courier_service': 'RM_SPECIAL_1PM',
        }
    },
    {
        'name': 'CR04 — DPD Next Day by 12PM',
        'rule_type': 'COURIER_SERVICE',
        'priority': 40,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'NEXT_DAY_12PM'},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_NEXT_DAY_12',
        }
    },
    {
        'name': 'CR05 — DPD Next Day (Next Day 1PM >3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 50,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'NEXT_DAY_1PM'},
                {'field': 'order.total_weight_g', 'op': 'gt', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_NEXT_DAY',
        }
    },
    {
        'name': 'CR06 — Royal Mail Special Saturday (Saturday ≤3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 60,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'SATURDAY'},
                {'field': 'order.total_weight_g', 'op': 'lte', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'ROYAL_MAIL',
            'set_courier_service': 'RM_SPECIAL_SAT',
        }
    },
    {
        'name': 'CR07 — DPD Saturday (Saturday >3kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 70,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'SATURDAY'},
                {'field': 'order.total_weight_g', 'op': 'gt', 'value': 3000},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_SAT',
        }
    },
    {
        'name': 'CR08 — DPD Parcel (Fleece ≥6 metres)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 80,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order_items.product_type', 'op': 'eq', 'value': 'Fleece'},
                {'field': 'order.total_metres', 'op': 'gte', 'value': 6},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_PARCEL',
        }
    },
    {
        'name': 'CR09 — Royal Mail Tracked 24 (Samples or small orders)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 90,
        'conditions': {
            'operator': 'OR',
            'checks': [
                {'field': 'order_items.product_type', 'op': 'eq', 'value': 'Sample'},
                {
                    'operator': 'AND',
                    'checks': [
                        {'field': 'order.total_weight_g', 'op': 'lte', 'value': 3000},
                        {'field': 'order.total_items', 'op': 'lte', 'value': 2},
                    ]
                }
            ]
        },
        'actions': {
            'set_courier_provider': 'ROYAL_MAIL',
            'set_courier_service': 'RM_TRACKED_24',
        }
    },
    {
        'name': 'CR10 — DPD Parcel Priority (Trade-only products)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 100,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order_items.product.trade_only_product', 'op': 'eq', 'value': True},
            ]
        },
        'actions': {
            'set_courier_provider': 'DPD',
            'set_courier_service': 'DPD_PARCEL_PRIORITY',
        }
    },
    {
        'name': 'CR11 — DHL Express EU',
        'rule_type': 'COURIER_SERVICE',
        'priority': 110,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'in', 'value': EU_COUNTRIES},
            ]
        },
        'actions': {
            'set_courier_provider': 'DHL',
            'set_courier_service': 'DHL_EXPRESS_EU',
        }
    },
    {
        'name': 'CR12 — DHL Express International (non-UK/EU)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 120,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'not_in', 'value': ['GB'] + EU_COUNTRIES},
            ]
        },
        'actions': {
            'set_courier_provider': 'DHL',
            'set_courier_service': 'DHL_EXPRESS_INTL',
        }
    },
    {
        'name': 'CR13 — Royal Mail International Tracked (international ≤2kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 115,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'not_eq', 'value': 'GB'},
                {'field': 'order.total_weight_g', 'op': 'lte', 'value': 2000},
            ]
        },
        'actions': {
            'set_courier_provider': 'ROYAL_MAIL',
            'set_courier_service': 'RM_INTL_TRACKED',
        }
    },
    {
        'name': 'CR14 — UPS Standard (UK >30kg)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 130,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.shipping_country', 'op': 'eq', 'value': 'GB'},
                {'field': 'order.total_weight_g', 'op': 'gt', 'value': 30000},
            ]
        },
        'actions': {
            'set_courier_provider': 'UPS',
            'set_courier_service': 'UPS_STANDARD',
        }
    },
    {
        'name': 'CR15 — Transglobal Economy (courier override)',
        'rule_type': 'COURIER_SERVICE',
        'priority': 140,
        'conditions': {
            'operator': 'AND',
            'checks': [
                {'field': 'order.delivery_type', 'op': 'eq', 'value': 'ECONOMY'},
                {'field': 'order.courier_override', 'op': 'eq', 'value': 'TRANSGLOBAL'},
            ]
        },
        'actions': {
            'set_courier_provider': 'TRANSGLOBAL',
            'set_courier_service': 'TG_ECONOMY',
        }
    },
]


class Command(BaseCommand):
    help = 'Seed the 15 predefined courier booking rules (CR01–CR15)'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for rule_data in RULES:
            _, was_created = Rule.objects.get_or_create(
                name=rule_data['name'],
                defaults={
                    'rule_type': rule_data['rule_type'],
                    'priority': rule_data['priority'],
                    'conditions': rule_data['conditions'],
                    'actions': rule_data['actions'],
                    'is_active': True,
                }
            )
            if was_created:
                created += 1
            else:
                skipped += 1
        self.stdout.write(self.style.SUCCESS(
            f'Done. {created} rules created, {skipped} already existed.'
        ))
```

---

## Summary Checklist

### New Apps to Create (10)
- [ ] `warehouse`
- [ ] `config`
- [ ] `audit`
- [ ] `shipping`
- [ ] `purchasing`
- [ ] `channels` (use `app_label = 'sales_channels'` due to Django Channels naming conflict)
- [ ] `rules`
- [ ] `mobile`
- [ ] `returns`
- [ ] `notifications`

### Existing Apps to Modify (4)
- [ ] `products` — Location model (3 new fields)
- [ ] `orders` — Order model (6 new fields), OrderItem (2 new fields), + 3 new models
- [ ] `stock` — StockItem (1 new field), + 3 new models
- [ ] `accounts` — UserType (1 new field), Profile (2 new fields)

### New Tables Summary (33 total)

| Table | App | Phase |
|---|---|---|
| `warehouse_zones` | warehouse | 1.1 |
| `api_credentials` | config | 1.2 |
| `system_config` | config | 1.2 |
| `print_config` | config | 1.2.1 |
| `audit_log` | audit | 1.3 |
| `courier_providers` | shipping | 2.1 |
| `courier_services` | shipping | 2.1 |
| `order_batches` | orders | 4.1 |
| `batch_orders` | orders | 4.1 |
| `order_exceptions` | orders | 4.2 |
| `order_notes` | orders | 4.3 |
| `stock_batches` | stock | 5.1 |
| `stocktakes` | stock | 5.2 |
| `stocktake_items` | stock | 5.2 |
| `suppliers` | purchasing | 6.1 |
| `purchase_orders` | purchasing | 6.1 |
| `po_items` | purchasing | 6.1 / 8 |
| `channels` | channels | 7.1 |
| `channel_mappings` | channels | 7.1 |
| `ingestion_logs` | channels | 7.1 |
| `channel_stock_sync_log` | channels | 7.2 |
| `courier_bookings` | shipping | 9.1 |
| `manifests` | shipping | 9.1 |
| `tracking_syncs` | shipping | 9.1 |
| `shipping_labels` | shipping | 9.2 |
| `print_jobs` | shipping | 9.2 |
| `rules` | rules | 10.1 |
| `rule_change_log` | rules | 10.1 |
| `qr_codes` | mobile | 11.1 |
| `processing_logs` | mobile | 11.1 |
| `pick_lists` | mobile | 11.2 |
| `pick_list_items` | mobile | 11.2 |
| `returns` | returns | 12.1 |
| `return_items` | returns | 12.1 |
| `notifications` | notifications | 13.1 |

### Infrastructure Requirements (Phase 0)
- [ ] PostgreSQL (replace SQLite)
- [ ] Redis (broker + cache + channel layers)
- [ ] Celery + django-celery-beat (scheduled tasks)
- [ ] Django Channels + channels-redis (WebSocket / real-time)
- [ ] python-qrcode + Pillow (QR code generation)
- [ ] WeasyPrint (PDF generation — pick lists, packing lists, manifests)
- [ ] Docker + Docker Compose (production deployment)

### Courier Booking Rules Seed (Phase 14)
- [ ] 15 rules seeded: CR01–CR15 via `python3 manage.py seed_courier_rules`

### Total New Tables: 35
### Total Modified Tables: 6
### Total New API Endpoint Groups: 26
