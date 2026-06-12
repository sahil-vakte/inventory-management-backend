# Cron Jobs

## Remote Tiaknight Order Import

Run every hour on the server:

```cron
0 * * * * mkdir -p /home/abhiwims/inventory-management-backend/logs && cd /home/abhiwims/inventory-management-backend && /home/abhiwims/inventory-management-backend/venv/bin/python manage.py import_remote_tiaknight_orders >> /home/abhiwims/inventory-management-backend/logs/remote_tiaknight_orders.log 2>&1
```

This uses the same import logic as:

```http
GET /api/v1/orders/import_from_remote_tiaknightfabrics/
```

Required `.env` values:

```env
TIA_URL=
TIA_CLIENTID=
TIA_USERNAME=
TIA_PASSWORD=
TIA_FILE_TYPE=xml
```

API-based cron is also possible, but it needs a valid JWT:

```cron
0 * * * * mkdir -p /home/abhiwims/inventory-management-backend/logs && curl -fsS -H "Authorization: Bearer YOUR_JWT_TOKEN" https://www.wims.cloud/api/v1/orders/import_from_remote_tiaknightfabrics/ >> /home/abhiwims/inventory-management-backend/logs/remote_tiaknight_orders_api.log 2>&1
```

The management-command cron is preferred because it does not depend on a JWT token expiring.
