# DPD Frontend Handover

## Purpose

The frontend must let a user book a DPD shipment only when WIMS selects DPD for the order, then open the printable label returned by WIMS. The frontend must not call DPD directly or construct DPD service/network codes.

Production base URL: `https://www.wims.cloud`

## Authentication

All WIMS order endpoints require the normal application bearer token, except the `public_label_url` returned after a successful booking.

```http
Authorization: Bearer <access_token>
```

## 1. Read the Order and Shipping Decision

```http
GET /api/v1/orders/{order_id}/
```

Use `shipping_service` from the response to decide what to display. Do not choose DPD from the frontend based on delivery text or weight.

Example:

```json
{
  "id": 3039,
  "status": "NEW",
  "shipping_service": {
    "provider": "DPD",
    "delivery_method": "NEXT DAY",
    "weight_in_grams": 3000,
    "shipment_type": "PARCEL",
    "service_code": "12",
    "network_code": "1^12",
    "booking_url": "/api/v1/orders/3039/book-dpd-shipping/"
  }
}
```

Show the DPD booking action only when `shipping_service.provider` is `"DPD"`.

## 2. Optional DPD Readiness Check

```http
GET /api/v1/orders/dpd/config/
```

Allow booking only when `booking_enabled` is `true`. This endpoint never returns credentials.

```json
{
  "configured": true,
  "booking_enabled": true,
  "api_mode": "dpd_uk",
  "message": "DPD Shipping API is configured."
}
```

## 3. Book a DPD Shipment

```http
POST /api/v1/orders/{order_id}/book-dpd-shipping/
Content-Type: application/json
```

Recommended request body:

```json
{
  "return_label_pdf": false,
  "notes": "Booked from WIMS"
}
```

WIMS resolves the order weight, shipment type, DPD service code, and DPD network code. The frontend normally should not send `weight_in_grams` or `service_code`.

For a deliberate test override only, these optional fields are accepted:

```json
{
  "weight_in_grams": 3000,
  "service_code": "12",
  "return_label_pdf": false,
  "notes": "DPD NEXT DAY test"
}
```

Keep `return_label_pdf` as `false` for the normal UI flow. A value of `true` returns the label itself as a binary response instead of the JSON response below.

## 4. Successful Booking Response

On HTTP `200`, WIMS has saved the label and marked the order as shipped.

```json
{
  "message": "DPD shipment booked, order marked as shipped, and label saved",
  "tracking_number": "15501234567890",
  "dpd_shipment_identifier": "shipment-uuid",
  "service_code": "12",
  "dpd_booking_options": {
    "weight_in_grams": 3000,
    "shipment_type": "PARCEL",
    "service_code": "12",
    "network_code": "1^12"
  },
  "label_url": "https://www.wims.cloud/api/v1/orders/3039/shipping-label/",
  "public_label_url": "https://www.wims.cloud/api/v1/orders/3039/shipping-label/public/<signed-token>/",
  "label_format": "pdf",
  "order": {
    "id": 3039,
    "status": "SHIPPED"
  }
}
```

Update the UI from the returned `order`, `tracking_number`, and `service_code`. Use `public_label_url` as the Print/Open Label action. It is a signed WIMS URL and does not need the frontend bearer token.

`label_format` can be `"pdf"` or `"html"`. Open the URL in a new tab and let the browser handle the returned content type; do not assume every DPD label is a PDF.

## 5. Existing Label and Duplicate Booking Protection

Disable the Book DPD button immediately while the request is pending. Do not retry a booking automatically.

When a user presses book for an order that has already been booked, WIMS returns HTTP `409` and does not call DPD again.

```json
{
  "error": "Shipment already booked for this order.",
  "message": "Order is already shipped, so DPD booking was not called again.",
  "tracking_number": "15501234567890",
  "carrier": "DPD",
  "label_url": "https://www.wims.cloud/api/v1/orders/3039/shipping-label/"
}
```

Another `409` can state that a shipping label already exists. In either case, refresh the order and show the existing print action instead of offering another booking attempt.

## 6. Error Handling

| HTTP status | Frontend action |
| --- | --- |
| `400` | Show the returned `error` and `message`. Booking may be disabled by configuration or the order may not be eligible. |
| `409` | Do not retry. Reload the order and use its existing label/tracking information. |
| `502` | Show the DPD error. Do not mark the UI as shipped. WIMS only marks an order shipped after it saves a printable label. |
| `401` or `403` | Refresh/login using the normal WIMS authentication flow. |

For a DPD provider error, keep the response data available in the frontend log/support view:

```json
{
  "error": "DPD returned HTTP 400",
  "dpd_status_code": 400,
  "dpd_booking_options": {
    "weight_in_grams": 3000,
    "shipment_type": "PARCEL",
    "service_code": "12",
    "network_code": "1^12"
  },
  "dpd_response": {}
}
```

## Current DPD Service Rules

WIMS applies these rules server-side:

| Delivery method | Weight | Shipment type | DPD service code |
| --- | --- | --- | --- |
| `STD` | 2501-30000 g | `PARCEL` | `11` |
| `NEXT DAY` | 1-30000 g | `PARCEL` | `12` |
| `NEXT DAY BY 12` | 2501-30000 g | `PARCEL` | `13` |
| `SATURDAY` | 2501-30000 g | `PARCEL` | `16` |
| `NEXT DAY BY 10:30` | 2501-30000 g | `PARCEL` | `14` |

The frontend should display the resolved `shipping_service` for clarity but leave rule enforcement and DPD request formatting to WIMS.

## Recommended Frontend Sequence

1. Load `GET /api/v1/orders/{order_id}/`.
2. Read `shipping_service`.
3. If the provider is `DPD`, show the DPD service and Book button.
4. Post the normal booking body with `return_label_pdf: false`.
5. On success, replace the button with tracking information and an Open/Print Label action using `public_label_url`.
6. On `409`, reload the order and show the existing shipment instead of booking again.
7. On `400` or `502`, show the error and leave the order unshipped in the UI.
