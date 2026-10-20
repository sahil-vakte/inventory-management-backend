# TODO 2026-10-16 - DHL Shipping Integration

## Goal

Integrate DHL shipment booking into WIMS so eligible orders can be booked,
labelled, tracked, and marked as shipped without leaving WIMS.

Royal Mail and DPD flows must remain unchanged. DHL is a third provider and
must only be selected when a DHL routing rule matches the order.

## Credentials Received

The client has supplied DHL API credentials and two DHL account numbers.

- Store the client ID and secret only in the server `.env` / secret manager.
- Do not commit credentials, access tokens, or raw DHL responses containing
  sensitive data.
- Confirm with DHL which account number applies to each service, destination,
  and environment (test or live).

Suggested environment variables:

```env
DHL_INTEGRATION_ENABLED=false
DHL_ENVIRONMENT=test
DHL_API_BASE_URL=
DHL_TOKEN_URL=
DHL_CLIENT_ID=
DHL_CLIENT_SECRET=
DHL_ACCOUNT_NUMBER=
DHL_LABEL_FORMAT=PDF
DHL_LABEL_SIZE=A6
DHL_SENDER_NAME=Civani Ltd
DHL_SENDER_COMPANY=Civani Ltd
DHL_SENDER_STREET=85 Commercial Square
DHL_SENDER_ADDRESS2=
DHL_SENDER_CITY=Leicester
DHL_SENDER_POSTCODE=LE2 7SR
DHL_SENDER_COUNTRY_CODE=GB
DHL_SENDER_CONTACT_NAME=
DHL_SENDER_PHONE=
DHL_SENDER_EMAIL=
```

## Information Still Needed From DHL / Client

1. The correct DHL API product and documentation URL.
   - Confirm whether this is DHL Express MyDHL API, DHL Parcel UK API, or
     another DHL product.
2. Test and production API base URLs.
3. OAuth token URL, required OAuth grant type, scopes, and required headers.
4. Confirmation that the supplied credentials are test or production
   credentials.
5. Which account number to use for domestic UK, EU, and international
   shipments.
6. DHL product/service codes enabled for the Civani account.
7. Collection / shipper address registered with DHL, including a valid contact
   name, telephone number, and email address.
8. Label endpoint or response format, including whether a label is returned in
   the shipment-create response or fetched separately.
9. Customs requirements for non-UK shipments: invoice, commodity code, item
   country of origin, declared value, currency, and terms of trade.
10. Required DHL test shipment addresses and any account approval needed before
    production booking.

## DHL Routing Rule Provided So Far

The initial DHL rule received is incomplete and must be confirmed before it is
enabled:

| Condition | Planned result |
| --- | --- |
| An order contains any item longer than 20 metres, except Fleece, Lace/Trimmings, or Elastic Tape | Candidate for DHL |
| Order weight is 6,000 to 30,000 grams | Candidate for DHL |
| Delivery method is `NEXT DAY` | DHL parcel shipment |

The DHL service/product code is still required. Do not route any order to DHL
until the product code and account mapping are confirmed.

## Proposed WIMS Flow

1. WIMS calculates total order weight in grams and reads order items,
   delivery method, destination country, and carrier.
2. Courier routing evaluates DHL rules before any booking request is made.
3. If a DHL rule matches, WIMS displays the planned DHL service in the order
   `shipping_service` response.
4. Warehouse calls a DHL booking endpoint for a completed order.
5. WIMS obtains an OAuth access token, creates the shipment, then retrieves the
   printable label if DHL returns it separately.
6. Only after a label is saved does WIMS save the DHL tracking number, carrier,
   shipping method, shipment reference, and change the order status to
   `SHIPPED`.
7. If DHL rejects the request or a printable label is unavailable, WIMS returns
   DHL's error and leaves the order unshipped.

## Planned API Surface

Configuration status:

```text
GET /api/v1/orders/dhl/config/
```

Book a DHL shipment:

```text
POST /api/v1/orders/{order_id}/book-dhl-shipping/
```

Initial WIMS request payload:

```json
{
  "weight_in_grams": 6500,
  "service_code": "",
  "notes": "DHL booking from WIMS",
  "return_label_pdf": true
}
```

`service_code` will be optional only when WIMS has a confirmed DHL routing
rule. Its accepted value must match the DHL product/service code confirmed for
the account.

Saved label download endpoint, shared with Royal Mail and DPD:

```text
GET /api/v1/orders/{order_id}/shipping-label/
```

## Implementation Status

- [x] Identified the supplied credential format as DHL Express MyDHL API with
  HTTP Basic authentication.
- [x] Added DHL configuration settings to `settings.py` and `.env.example`.
- [x] Added `orders/services/dhl.py` for MyDHL shipment creation, inline PDF
  label extraction, routing, and error parsing.
- [x] Added a non-secret DHL configuration-status endpoint.
- [x] Added `POST /api/v1/orders/{order_id}/book-dhl-shipping/`.
- [x] Reused the existing saved-label and public-label mechanisms.
- [x] Save DHL tracking number, carrier (`DHL`), product code, shipment
  reference note, and label before marking the order as shipped.
- [x] Added the supplied DHL routing rule: qualifying long item, 6000-30000g,
  and `NEXT DAY` delivery.
- [x] Included DHL in the computed `shipping_service` field in order list and
  detail responses.
- [x] Updated `POSTMAN_COLLECTION_COMPLETE.json` with DHL config, booking, and
  label requests.
- [x] Added focused tests for routing, Basic authentication, payload mapping,
  labels, successful shipment status update, and status guardrails.
- [ ] Set the DHL product code enabled on the Civani account before deployment.

## Acceptance Criteria

- DHL is never chosen until a confirmed DHL rule matches the order.
- Existing Royal Mail and DPD booking flows continue to work unchanged.
- A successful DHL booking saves a printable label and tracking data, then
  marks the order as `SHIPPED`.
- A failed booking does not change the order to `SHIPPED`.
- Credentials and access tokens never appear in API responses, Git, or logs.
- Postman contains safe DHL requests using environment variables, not secrets.

## Deployment Checklist

- [ ] Populate DHL credentials in the server secret store / `.env`.
- [ ] Set `DHL_INTEGRATION_ENABLED=false` initially.
- [ ] Verify `/api/v1/orders/dhl/config/` reports the expected non-secret
  configuration fields.
- [ ] Run a DHL test shipment using DHL's approved test order/address.
- [ ] Verify label, tracking number, and order status in WIMS.
- [ ] Confirm shipment visibility in the DHL test portal.
- [ ] Enable production only after DHL confirms the live account and service
  code.
