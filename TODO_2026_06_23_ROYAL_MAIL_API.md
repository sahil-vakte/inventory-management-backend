# TODO 2026-06-23 - Royal Mail Click & Drop API Integration

## Extracted From Screenshot

### Account / Login

- Service: Royal Mail Click & Drop
- Login host: `auth.parcel.royalmail.com`
- Login URL: `https://auth.parcel.royalmail.com/?clientReturnUrl=%2F`
- Account email / username: `info@civani.co.uk`
- Password: keep only in local `.env` or server secret manager. Do not commit plaintext credentials.
- Current limitation: the screenshot does not include a Click & Drop API key.

### API / Documentation URLs

- API base URL: `https://api.parcel.royalmail.com/`
- Help article: `https://help.parcel.royalmail.com/hc/en-gb/articles/360011462338-Integrating-with-the-Click-Drop-API`
- Help host: `help.parcel.royalmail.com`

## Environment Variables To Add

- `ROYAL_MAIL_API_BASE_URL=https://api.parcel.royalmail.com/api/v1`
- `ROYAL_MAIL_AUTH_URL=https://auth.parcel.royalmail.com/`
- `ROYAL_MAIL_USERNAME=info@civani.co.uk`
- `ROYAL_MAIL_PASSWORD=<store securely, do not commit>`
- `ROYAL_MAIL_API_KEY=<must be generated/confirmed from Click & Drop dashboard>`

## Implementation TODO

- [ ] Generate/confirm Click & Drop API key value from Royal Mail account/dashboard.
- [x] Confirm Click & Drop API authentication method from Royal Mail documentation.
- [x] Confirm whether API uses API key, OAuth, or account login credentials.
- [x] Add Royal Mail settings to Django settings via environment variables only.
- [x] Create a Royal Mail service/client module for API calls.
- [x] Add request/response logging without logging secrets.
- [x] Add API error handling for authentication failures, validation errors, and rate limits.
- [x] Add shipping-booking flow once required Royal Mail API fields are confirmed.
- [x] Store Royal Mail tracking number, carrier, shipping method, and booking reference against orders.
- [x] Update order status to `SHIPPED` once shipping is successfully booked via API.
- [x] Add Postman requests for Royal Mail config/test status and shipment booking once endpoints are implemented.
- [x] Add tests with mocked Royal Mail API responses.
- [x] Support the current available-data state: login credentials present, booking disabled until API key exists.

## Implemented Endpoints

- `GET /api/v1/orders/royal-mail/config/`
- `POST /api/v1/orders/{order_id}/book-royal-mail-shipping/`

`GET /api/v1/orders/royal-mail/config/` reports:

- Whether login credentials are present.
- Whether `ROYAL_MAIL_API_KEY` is present.
- Whether booking is currently enabled.

Shipment booking requires `ROYAL_MAIL_API_KEY`. The login email/password alone are not sent to the API booking endpoint.

Example shipment payload:

```json
{
  "weight_in_grams": 250,
  "package_format_identifier": "Parcel",
  "service_code": "TPLN",
  "notes": "Booked through Royal Mail Click & Drop API"
}
```

## Safety Notes

- Never hardcode Royal Mail password or API key in code, docs, migrations, tests, or Postman collections.
- Keep real credentials only in `.env` on local/server or a proper secret manager.
- Use redacted values in logs and API responses.
