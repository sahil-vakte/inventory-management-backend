# Royal Mail Click & Drop Notes

## Can We Send Orders Without API Key?

No, not through the Royal Mail Click & Drop API.

The login email/password can be used to sign in manually here:

- `https://auth.parcel.royalmail.com/?clientReturnUrl=%2F`

But the backend API integration needs a Click & Drop API key:

- `ROYAL_MAIL_API_KEY`

Without this API key, our backend cannot create shipments, generate labels, or receive tracking/reference data from Royal Mail automatically.

## What We Can Do With Only Login Credentials

- Log in manually to Royal Mail Click & Drop.
- Create labels manually from the Royal Mail website.
- Check Royal Mail account/dashboard manually.
- Generate or find the Click & Drop API key if the account has API access enabled.

## What We Cannot Do Without API Key

- Send order data from WIMS backend to Royal Mail automatically.
- Book shipment through API.
- Generate label through API.
- Get tracking number/reference back through API.
- Automatically mark order as `SHIPPED` after Royal Mail booking.

## Current Backend Behavior

Config check:

```http
GET /api/v1/orders/royal-mail/config/
```

Expected response with current data:

```json
{
  "configured": false,
  "booking_enabled": false,
  "api_base_url": "https://api.parcel.royalmail.com/api/v1",
  "auth_url": "https://auth.parcel.royalmail.com",
  "username": "info@civani.co.uk",
  "login_credentials_present": true,
  "default_package_format": "Parcel",
  "default_weight_grams": 100,
  "api_key_present": false,
  "api_key_required_for_booking": true,
  "message": "Royal Mail login credentials are present, but shipment booking requires a Click & Drop API key."
}
```

## Response If We Try To Send Order Without API Key

Request:

```http
POST /api/v1/orders/{order_id}/book-royal-mail-shipping/
```

Payload:

```json
{
  "weight_in_grams": 250,
  "package_format_identifier": "Parcel",
  "service_code": "TPLN",
  "notes": "Booked through Royal Mail Click & Drop API"
}
```

Response:

```json
{
  "error": "ROYAL_MAIL_API_KEY is not configured",
  "message": "Only Royal Mail login credentials are configured. Generate a Click & Drop API key from the Royal Mail account and set ROYAL_MAIL_API_KEY.",
  "auth_url": "https://auth.parcel.royalmail.com",
  "username": "info@civani.co.uk"
}
```

## Response After Successful Royal Mail Booking

After `ROYAL_MAIL_API_KEY` is added and Royal Mail accepts the order, our backend response will look like this:

```json
{
  "message": "Royal Mail shipment booked and order marked as shipped",
  "tracking_number": "RMTRACK123",
  "royal_mail_reference": "RM-ORDER-1",
  "royal_mail_response": {
    "items": [
      {
        "orderIdentifier": "RM-ORDER-1",
        "trackingNumber": "RMTRACK123"
      }
    ]
  },
  "order": {
    "id": 10,
    "order_status": "SHIPPED",
    "order_status_display": "Shipped",
    "carrier": "Royal Mail",
    "tracking_number": "RMTRACK123",
    "shipping_method": "TPLN"
  }
}
```

Actual Royal Mail response fields may differ slightly depending on the Click & Drop API response, but our backend will try to extract:

- Tracking number
- Royal Mail order/reference identifier
- Full Royal Mail response

Then it updates our order to:

- `carrier = Royal Mail`
- `tracking_number = <Royal Mail tracking number>`
- `shipping_method = <service_code>`
- `order_status = SHIPPED`
