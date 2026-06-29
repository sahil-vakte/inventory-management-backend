# TODO 2026-06-29 - DPD / MyDPD Shipping Integration

## Goal

Integrate DPD/MyDPD shipping into WIMS so shipment booking can work based on the order `carrier`.

Current Royal Mail flow should stay available, but when an order is assigned to DPD, WIMS should use DPD instead of Royal Mail.

## User Requirement

- Integrate `https://myaddressbook.dpd.co.uk/`
- DPD should work instead of Royal Mail based on the order `carrier`
- Store DPD booking/label/tracking data in WIMS order details
- Use this for the next shipping-booking phase

## Important Clarification Needed

`https://myaddressbook.dpd.co.uk/` is a MyDPD address book portal, not necessarily the shipment booking API itself.

There are two likely integration paths:

1. MyDPD Address Book / CSV import flow
   - WIMS exports customer/order address data in the MyDPD Address Book format.
   - User imports the file into MyDPD manually or semi-automatically.
   - Useful if API access is not available yet.

2. DPD UK API shipment booking flow
   - WIMS sends shipment data directly to DPD API.
   - DPD returns shipment/label/tracking data.
   - This is the proper automated replacement for Royal Mail booking.

Client must confirm which access is available.

## Official References

- MyDPD Address Book: `https://myaddressbook.dpd.co.uk/`
- MyDPD Address Book specification: `https://help.dpd.co.uk/mydpd/user_guides/address_book/mydpd_address_book_spec_v3_0.pdf`
- DPD API documentation: `https://www.dpd.com/wp-content/uploads/sites/235/2023/04/DPD-API-documentation-v1-2-1.pdf`
- DPD Shipping API docs: `https://shipping.dpdgroup.com/api/v1.1/`

## Credentials / Information Needed From Client

For MyDPD Address Book export/import:

- MyDPD login URL/account confirmation
- Required Address Book import mapping
- Required CSV delimiter
- Required field order
- Any sender/return address defaults
- Whether Short Name should be order number, external order id, or customer name

For DPD API booking:

- DPD API base URL
- Username / account login
- Password or API secret/token process
- Customer account number, if required
- Collection/sender address details
- Default service codes
- Test/production mode confirmation
- Label format requirement: PDF, PNG, ZPL, etc.
- Whether DPD requires label approval before live shipping

## Proposed WIMS Flow

1. Order is imported from Tiaknight.
2. Tiaknight courier data is saved in:
   - `courier_service_name`
   - `courier_service_code`
   - `carrier`
3. When warehouse books shipment:
   - If `carrier = Royal Mail`, use Royal Mail booking service.
   - If `carrier = DPD`, use DPD booking service.
   - If carrier is missing or unsupported, return a clear validation error.
4. On successful booking:
   - Save tracking number.
   - Save carrier.
   - Save shipping method/service code.
   - Save shipment reference.
   - Save label URL/file reference if returned.
   - Mark order as `SHIPPED`.
5. On failed booking:
   - Do not mark order as shipped.
   - Store/return DPD error response.
   - Keep order in `COMPLETED`.

## Database Changes To Plan

Current order fields already support part of this:

- `carrier`
- `shipping_method`
- `tracking_number`
- `courier_service_name`
- `courier_service_code`

Add if needed:

- `shipment_provider`
- `shipment_reference`
- `shipment_label_url`
- `shipment_label_file`
- `shipment_booked_at`
- `shipment_raw_response`

Better long-term model:

- Create `ShippingBooking` table
  - `order`
  - `provider` - Royal Mail / DPD
  - `carrier`
  - `service_code`
  - `tracking_number`
  - `shipment_reference`
  - `label_url`
  - `label_file`
  - `status`
  - `request_payload`
  - `response_payload`
  - `booked_by`
  - `booked_at`

This prevents mixing every carrier-specific value into the main `orders` table.

## API Changes To Plan

Option A - Carrier-specific APIs:

- `POST /api/v1/orders/{order_id}/book-royal-mail-shipping/`
- `POST /api/v1/orders/{order_id}/book-dpd-shipping/`

Option B - Unified API, preferred:

- `POST /api/v1/orders/{order_id}/book-shipping/`

Payload:

```json
{
  "carrier": "DPD",
  "service_code": "NEXT_DAY",
  "weight_in_grams": 500,
  "package_format_identifier": "Parcel",
  "notes": "Booked from WIMS"
}
```

If `carrier` is omitted, WIMS uses the order `carrier`.

## DPD Address Book Export Fields

Create an export file using order/customer address data.

Suggested fields from MyDPD Address Book specification:

- Short Name
- Country
- Postal/Zip Code
- Organisation/Name
- Delivery Address Line 1
- Delivery Address Line 2
- Town/City
- County/State
- Contact
- Telephone
- Address Type
- Notification Email
- Notification Text
- Delivery Information
- Reference 1
- Reference 2
- Reference 3

Recommended mapping:

- Short Name: `external_order_id`
- Organisation/Name: `customer_name`
- Postal/Zip Code: `shipping_postal_code`
- Delivery Address Line 1: `shipping_address_line1`
- Delivery Address Line 2: `shipping_address_line2`
- Town/City: `shipping_city`
- County/State: `shipping_state`
- Telephone: `customer_phone`
- Notification Email: `customer_email`
- Reference 1: `external_order_id`
- Reference 2: `order_number`
- Reference 3: `courier_service_code`

## Carrier Routing Logic

Normalize carrier values before routing:

- `royal mail`
- `royalmail`
- `rm`
- `dpd`
- `dpd uk`
- `mydpd`

Rules:

- Royal Mail values -> Royal Mail API client
- DPD values -> DPD API client or MyDPD export
- Unknown values -> return validation error with supported carriers

## DPD Service Mapping To Confirm

Need client/DPD account service codes for:

- Standard Delivery
- Next Day
- Next Day By 12
- Saturday Delivery
- International
- Europe
- Collect in Store

Do not guess final DPD service codes until DPD confirms account-enabled services.

## Implementation Tasks

1. Confirm DPD integration mode:
   - MyDPD Address Book export only
   - Direct DPD API booking
   - Both

2. Add environment variables:

```env
DPD_INTEGRATION_ENABLED=false
DPD_MODE=address_book
DPD_API_BASE_URL=
DPD_USERNAME=
DPD_PASSWORD=
DPD_ACCOUNT_NUMBER=
DPD_DEFAULT_SERVICE_CODE=
DPD_DEFAULT_PACKAGE_FORMAT=Parcel
DPD_DEFAULT_WEIGHT_GRAMS=100
DPD_LABEL_FORMAT=PDF
```

3. Create DPD service/client:
   - `orders/services/dpd.py`
   - Authentication/login
   - Create shipment
   - Parse tracking/reference/label response
   - Raise errors without marking shipped

4. Create carrier router:
   - `orders/services/shipping_router.py`
   - Decide provider from order `carrier`
   - Dispatch to Royal Mail or DPD

5. Create unified shipping endpoint:
   - `POST /api/v1/orders/{order_id}/book-shipping/`
   - Keep Royal Mail endpoint for backward compatibility

6. Add MyDPD Address Book export endpoint if needed:
   - `GET /api/v1/orders/dpd-address-book-export/`
   - Supports filters like `order_status`, `date_from`, `date_to`, `carrier`

7. Update order response:
   - Include shipment provider/reference/label fields if new model/table is added
   - Keep `carrier`, `shipping_method`, `tracking_number`, `courier_service_name`, `courier_service_code`

8. Update Postman collection:
   - DPD config/status
   - Book shipping unified API
   - Book DPD shipping API if separate
   - MyDPD address book export

9. Add tests:
   - DPD route selected when carrier is DPD
   - Royal Mail route selected when carrier is Royal Mail
   - Unknown carrier rejected
   - DPD API failure does not mark order shipped
   - DPD success marks order shipped and saves tracking/reference
   - Address book export contains correct fields

## Acceptance Criteria

- Royal Mail still works as it does now.
- DPD orders do not go to Royal Mail.
- DPD failed bookings do not mark orders as shipped.
- Successful DPD bookings save shipment details in WIMS.
- Order API response shows carrier and shipment details.
- Label/address export uses `external_order_id` as the main order reference.
- Postman collection has DPD requests.

## Deployment Notes

- Do not enable DPD booking until credentials/service codes are confirmed.
- Start with `DPD_INTEGRATION_ENABLED=false`.
- Test using one completed order before enabling for live workflow.
- If direct DPD API is used, confirm whether DPD needs test label approval before live shipments.
