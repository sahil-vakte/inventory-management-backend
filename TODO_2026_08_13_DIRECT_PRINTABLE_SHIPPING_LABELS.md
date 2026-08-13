# TODO - Direct Printable Shipping Labels

Date: 2026-08-13

## Goal

Create a direct shipping flow inside WIMS where users can book a carrier shipment from an order and immediately receive a printable label file without logging into Royal Mail Click & Drop or DPD manually.

## Current Position

- WIMS already stores order, customer, address, delivery method, order items, item weight, and total order weight.
- Royal Mail Click & Drop API key based integration is the first carrier flow.
- DPD integration will be added later and selected based on order carrier.
- Royal Mail service/package selection rules have started from the provided criteria sheet.

## Royal Mail Flow

1. User opens an order in WIMS.
2. User clicks `Book Shipment` or `Generate Label`.
3. Backend validates required order data:
   - external order id
   - customer name
   - delivery address
   - postcode
   - delivery method
   - total weight in grams
   - order items
4. Backend resolves Royal Mail package and service code:
   - STD + up to 100g => Letter + STL2
   - STD + 101g to 500g => Large Letter + TRS48
   - STD + 501g to 2500g => Parcel + TPS48
   - NEXT DAY + supported criteria => TRN24 or TPN24
   - Fleece + STD + up to 5m => Parcel + TPS48
5. Backend sends shipment/order booking request to Royal Mail.
6. Backend saves returned Royal Mail data:
   - royal mail reference
   - tracking number
   - selected service code
   - package format identifier
   - label id or label file reference
   - raw booking response if useful for debugging
7. Backend downloads or exposes the printable label file.
8. WIMS order is marked as shipped only after successful carrier booking.
9. API response returns label URL/file info to frontend.

## Required APIs

### Book Royal Mail Shipment

Existing endpoint:

```http
POST /api/v1/orders/{order_id}/book-royal-mail-shipping/
```

Expected behavior:

- Use order data from DB.
- Allow optional override for weight/package/service.
- Convert internal delivery codes like `STD` into valid Royal Mail service codes.
- Do not send invalid internal codes to Royal Mail.
- Save carrier response.
- Return printable label URL when available.

Example response:

```json
{
  "message": "Shipment booked successfully",
  "order_id": 902,
  "external_order_id": "WEB236470",
  "tracking_number": "AB123456789GB",
  "royal_mail_reference": "WEB236470",
  "service_code": "STL2",
  "package_format_identifier": "Letter",
  "label_url": "https://www.wims.cloud/api/v1/orders/902/shipping-label/"
}
```

### Download Shipping Label

New or existing endpoint to confirm:

```http
GET /api/v1/orders/{order_id}/shipping-label/
```

Expected behavior:

- Return PDF or carrier label file directly.
- Support browser print/download.
- Return clear error if label has not been generated.

## Data Model Updates To Check

- Confirm where to save label file path or external label id.
- Confirm where to save carrier booking response.
- Confirm order has these fields or add safely if missing:
  - carrier
  - courier_service_name
  - courier_service_code
  - shipping_method
  - tracking_number
  - royal_mail_reference
  - shipping_label_url or shipping_label_file
  - shipped_at

## DPD Future Flow

1. Add DPD credentials in `.env`.
2. Add DPD API client/service.
3. Use same WIMS button and same backend flow.
4. Select carrier by order carrier field.
5. If carrier is Royal Mail, use Royal Mail client.
6. If carrier is DPD, use DPD client.
7. Save tracking and printable label file the same way.

## Information Needed From Carrier/Client

Royal Mail:

- Confirm Click & Drop API key is active.
- Confirm account supports label/document retrieval.
- Confirm enabled service codes for the account.
- Confirm supported label format: PDF, PNG, ZPL, or 6x4 thermal.
- Confirm reprint and cancel shipment endpoints.

DPD:

- API credentials.
- Shipment booking endpoint.
- Label download endpoint.
- Service code list.
- Test/sandbox details if available.
- Required package dimensions/weight rules.

## International Order Checks

Before enabling direct labels for international orders, confirm required customs data:

- customs description
- item value
- item weight
- HS code
- country of origin
- EORI/IOSS where required
- recipient phone/email requirements

## Validation Rules

- Do not book shipment if address is incomplete.
- Do not mark order as shipped if carrier booking fails.
- Do not create duplicate carrier shipment for already booked order unless explicitly rebooked.
- Allow label reprint without creating a new shipment.
- Store errors clearly for debugging.

## Postman Updates Needed

- Add/verify Royal Mail book shipment endpoint.
- Add/verify shipping label download endpoint.
- Add example for auto criteria with STD and 100g.
- Add example for label reprint.
- Add future DPD folder only after DPD implementation starts.

## Testing Checklist

- Book STD order up to 100g and verify Royal Mail receives STL2 + Letter.
- Book STD order 101g to 500g and verify TRS48 + Large Letter.
- Book STD order 501g to 2500g and verify TPS48 + Parcel.
- Verify response contains label URL/file info.
- Verify order status becomes Shipped only after successful booking.
- Verify duplicate booking is prevented.
- Verify label can be downloaded/printed.
- Verify failed carrier response does not change order status.
