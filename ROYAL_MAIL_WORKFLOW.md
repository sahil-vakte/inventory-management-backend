# Royal Mail Workflow

## Purpose

Royal Mail Click & Drop is used to book shipping for completed WIMS orders.

The system supports two Royal Mail authentication methods:

1. `ROYAL_MAIL_API_KEY`, if available.
2. Royal Mail OAuth connection, if API key is not available.

The API key is used first when configured. If the API key is empty, the system uses the saved OAuth token.

## Step 1 - Connect Royal Mail

Call:

```http
GET {{base_url}}/api/v1/orders/royal-mail/oauth/start/
```

Response gives an `authorization_url`.

Open `authorization_url` in the browser, then log in to Royal Mail Click & Drop and approve WIMS.

## Step 2 - Royal Mail Callback

After approval, Royal Mail redirects to:

```http
https://www.wims.cloud/auth/royalmail/callback?code=...
```

The backend receives the `code`, exchanges it with Royal Mail, and saves the OAuth token in the database.

Tokens and secrets are not returned in API responses.

## Step 3 - Check Royal Mail Connection

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

You can also check the full Royal Mail configuration status:

```http
GET {{base_url}}/api/v1/orders/royal-mail/config/
```

Important response fields:

```json
{
  "configured": true,
  "booking_enabled": true,
  "auth_mode": "oauth",
  "oauth_connected": true
}
```

`auth_mode` can be:

- `api_key`
- `oauth`
- `not_configured`

## Step 4 - Complete Order Before Shipping

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

## Step 5 - Book Royal Mail Shipment

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

## Step 6 - Data Sent To Royal Mail

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

## Step 7 - After Successful Booking

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

## Step 8 - Check Updated Order

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

## Disconnect Royal Mail OAuth

If needed, deactivate saved Royal Mail OAuth tokens:

```http
POST {{base_url}}/api/v1/orders/royal-mail/oauth/disconnect/
```

This does not delete old records. It only marks saved OAuth tokens as inactive.

## Server Deployment Steps

After pushing code to server:

```bash
git pull origin main
python manage.py migrate
sudo supervisorctl restart inventory
```

Required server environment variables:

```env
ROYAL_MAIL_CLIENT_ID=<client-id>
ROYAL_MAIL_CLIENT_SECRET=<client-secret>
ROYAL_MAIL_OAUTH_CALLBACK_URL=https://www.wims.cloud/auth/royalmail/callback
ROYAL_MAIL_OAUTH_AUTHORIZATION_URL=https://auth.parcel.royalmail.com/oauth2/authorize
ROYAL_MAIL_OAUTH_TOKEN_URL=https://auth.parcel.royalmail.com/oauth2/token
ROYAL_MAIL_OAUTH_SCOPE=
```

Do not commit real secrets to git.
