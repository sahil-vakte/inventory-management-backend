# Tiaknight Missing Orders Notes

## Problem

Some Tiaknight order numbers were missing in WIMS even though nearby order numbers were imported.

Reported missing examples:

```text
WEB235979
WEB235986
WEB235987
```

## Server Findings

On the server, these orders were not found in WIMS:

- Not in `external_order_id`
- Not in `order_number`
- Not in internal notes
- Not soft deleted

The hourly Tiaknight cron was running successfully.

Import logs showed:

```text
orders_failed: 0
```

So the parser did not fail while importing those orders.

## Important Finding

The live Tiaknight SOAP response did not contain the missing orders.

Current `GetNewOrders` response had later/nearby orders, for example:

```text
WEB235991
WEB235992
WEB235993
WEB235995
```

But it did not contain:

```text
WEB235979
WEB235986
WEB235987
```

## Likely Causes

Possible causes are on the Tiaknight/source side:

1. The orders were already marked as downloaded/exported in Tiaknight.
2. Another system, user, or integration pulled those orders before WIMS.
3. The orders had a status that is not returned by `GetNewOrders`.
4. Tiaknight's `GetNewOrders` cursor skipped them after a previous request.
5. The orders were created/changed in Tiaknight in a way that did not make them available to the SOAP feed.

## Why This Is Not A WIMS Parser Error

If WIMS received the orders and failed to import them, the cron log would show failed orders or parser errors.

But the logs showed:

```text
orders_failed: 0
```

Also, the missing order references were not present in the SOAP payload checked later.

## Recovery Options

To recover missing orders:

1. Check those order numbers in Tiaknight admin.
2. Confirm their order status.
3. Confirm whether they are marked downloaded/exported.
4. Ask Tiaknight/client to re-release or mark them as not downloaded.
5. If possible, get XML export for those specific orders and import manually into WIMS.

## Improvement Added

We added audit logging for every Tiaknight SOAP pull.

New audit log:

```text
logs/remote_tiaknight_order_refs.log
```

Each run records:

- timestamp
- HTTP status
- Tiaknight request ID
- Tiaknight source datetime
- `TIA_AUTO_UPDATE`
- file type
- total orders received
- all order references received

Example:

```text
[2026-06-27 16:00:13 UTC] http_status=200 request_id=946 source_datetime=2026-06-27 16:50:45 auto_update=false file_type=xml orders_received=29 refs=WEB235991,WEB235992,WEB235993
```

## How To Check Next Time

Search the audit log:

```bash
grep WEB235979 logs/remote_tiaknight_order_refs.log
```

If the order appears in this log:

```text
Tiaknight sent it to WIMS.
```

Then we check parser/import logic.

If the order does not appear:

```text
Tiaknight did not send it to WIMS.
```

Then the issue is with the source/export state.

## Server Env

Keep this on the server:

```env
TIA_AUTO_UPDATE=false
TIA_FILE_TYPE=xml
TIA_AUDIT_LOG_PATH=logs/remote_tiaknight_order_refs.log
TIA_SAVE_RAW_PAYLOAD=false
TIA_RAW_PAYLOAD_DIR=logs/tiaknight_payloads
```

`TIA_AUTO_UPDATE=false` means WIMS does not ask Tiaknight to mark orders as downloaded.
