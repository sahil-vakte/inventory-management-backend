# Royal Mail Workflow

## Purpose

Royal Mail Click & Drop is used to book shipping for completed WIMS orders.

The system uses the Royal Mail Click & Drop API authorisation key:

```env
ROYAL_MAIL_API_KEY=<click-drop-api-authorisation-key>
```

Client ID/client secret are not used for this Option 1 integration.

## Current Recommended Setup - API Key

Royal Mail's Click & Drop API documentation says requests are authenticated using a Click & Drop API authorisation key in the `Authorization` header.

To get it:

1. Log in to Royal Mail Click & Drop.
2. Go to `Settings` > `Integrations`.
3. Select or create `Click & Drop API`.
4. Expand the integration row.
5. Copy the displayed authorisation key.
6. Set it on the server:

```env
ROYAL_MAIL_API_KEY=<click-drop-api-authorisation-key>
```

Then restart the backend.

The screenshot error `the page cannot be found` happens because Royal Mail does not expose the guessed OAuth URL:

```text
https://auth.parcel.royalmail.com/oauth2/authorize
```

Do not use the OAuth start endpoint for Option 1.

## Step 2 - Check Royal Mail Configuration

Call:

```http
GET {{base_url}}/api/v1/orders/royal-mail/oauth/status/
```

Expected connected response:

```json
{
  "connected": true
}
```

```http
GET {{base_url}}/api/v1/orders/royal-mail/config/
```

Important response fields:

```json
{
  "configured": true,
  "booking_enabled": true,
  "auth_mode": "api_key",
  "api_key_present": true,
  "api_key_required_for_booking": true
}
```

## Step 3 - Complete Order Before Shipping

Royal Mail shipment booking is allowed only when the order is completed.

Order status flow:

1. `New`
2. `Label Printed`
3. `In Progress`
4. `Completed`
5. `Shipped`
6. `Cancelled`

Before booking Royal Mail shipping, order status must be:

```text
Completed
```

## Step 4 - Book Royal Mail Shipment

Call:

```http
POST {{base_url}}/api/v1/orders/{{order_id}}/book-royal-mail-shipping/
```

Sample payload:

```json
{
  "weight_in_grams": 250,
  "package_format_identifier": "Parcel",
  "service_code": "TPLN",
  "notes": "Booked through Royal Mail"
}
```

## Step 5 - Data Sent To Royal Mail

The backend sends order details to Royal Mail, including:

- Order number
- Customer name
- Customer phone
- Customer email
- Shipping address
- Order date
- Subtotal
- Shipping cost
- Total amount
- Currency code
- Package weight
- Package format
- Order items
- Item SKU
- Item product name
- Item quantity
- Item unit value

## Step 6 - After Successful Booking

If Royal Mail accepts the shipment booking, WIMS updates the local order.

Updated fields:

```text
order_status = Shipped
carrier = Royal Mail
tracking_number = Royal Mail tracking number, if returned
shipping_method = service_code, if provided
internal_notes = Royal Mail reference and booking note
shipped_date = current date/time
```

The booking API response includes:

```json
{
  "message": "Royal Mail shipment booked and order marked as shipped",
  "tracking_number": "...",
  "royal_mail_reference": "...",
  "royal_mail_response": {},
  "order": {}
}
```

## Step 7 - Check Updated Order

Call:

```http
GET {{base_url}}/api/v1/orders/{{order_id}}/
```

Expected order fields:

```json
{
  "order_status": "SHIPPED",
  "order_status_display": "Shipped",
  "carrier": "Royal Mail",
  "tracking_number": "..."
}
```

## Server Deployment Steps

After pushing code to server:

```bash
git pull origin main
python manage.py migrate
sudo supervisorctl restart inventory
```

Required server environment variables for API-key mode:

```env
ROYAL_MAIL_API_KEY=<click-drop-api-authorisation-key>
```

Do not commit real secrets to git.
