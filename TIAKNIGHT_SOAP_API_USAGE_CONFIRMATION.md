# Tiaknight SOAP API Usage Confirmation

Date: 2026-08-15

WIMS is currently integrated with Tiaknight using the SOAP API below.

## API Details

- API type: SOAP
- SOAP version used by WIMS: SOAP 1.1
- Endpoint:

```text
https://www.tiaknightfabrics.co.uk/api/soap/service/6
```

- Operations currently used:

```text
GetNewOrders
GetOrder
```

- Request content type:

```text
text/xml; charset=utf-8
```

- SOAP envelope namespace used:

```text
http://schemas.xmlsoap.org/soap/envelope/
```

This namespace confirms that WIMS is sending SOAP 1.1 style requests.

Tiaknight service namespace:

```text
https://www.tiaknightfabrics.co.uk/api/soap/service/6
```

## Authentication

WIMS sends Tiaknight credentials in the SOAP header using:

```xml
<ser:VSAuth>
  <ClientID>...</ClientID>
  <Username>...</Username>
  <Password>...</Password>
</ser:VSAuth>
```

Actual credentials are stored in WIMS server environment variables and are not included in this document.

## Current Request Shape

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope
 xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
 xmlns:ser="https://www.tiaknightfabrics.co.uk/api/soap/service/6">
  <soapenv:Header>
    <ser:VSAuth>
      <ClientID>...</ClientID>
      <Username>...</Username>
      <Password>...</Password>
    </ser:VSAuth>
  </soapenv:Header>
  <soapenv:Body>
    <ser:GetNewOrders>
      <auto_update>false</auto_update>
      <file_type>xml</file_type>
    </ser:GetNewOrders>
  </soapenv:Body>
</soapenv:Envelope>
```

## GetOrder Detail Enrichment

WIMS now optionally fetches full order details for every order reference returned by `GetNewOrders`.

This is controlled by:

```env
TIA_FETCH_ORDER_DETAILS=true
```

For each order, WIMS sends:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="https://www.tiaknightfabrics.co.uk/api/soap/service/6">
  <soapenv:Header>
    <ser:VSAuth>
      <ClientID>...</ClientID>
      <Username>...</Username>
      <Password>...</Password>
    </ser:VSAuth>
  </soapenv:Header>
  <soapenv:Body>
    <ser:GetOrder>
      <order_ref>WEB238336</order_ref>
      <order_id>238336</order_id>
    </ser:GetOrder>
  </soapenv:Body>
</soapenv:Envelope>
```

The `GetOrder` result replaces the lightweight `GetNewOrders` row before import when a matching full order is returned.

## Personalisation Handling

WIMS now parses Tiaknight v6 nested personalisation blocks:

```xml
<PERSONALISATIONS>
  <PERSONALISATION>
    <TITLE>Custom Cutting</TITLE>
    <DETAILS>
      <DETAIL>
        <FIELD>Enter your custom cutting requirements</FIELD>
        <VALUE>3mx2</VALUE>
      </DETAIL>
    </DETAILS>
  </PERSONALISATION>
</PERSONALISATIONS>
```

Saved into WIMS order item fields:

```text
summary = Custom Cutting
personalization = Custom Cutting: Enter your custom cutting requirements = 3mx2
```

These fields are returned in:

```text
GET /api/v1/orders/{order_id}/
GET /api/v1/orders/with-items/
GET /api/v1/order-items/
GET /api/v1/orders/label-excel/
```

## Remaining Confirmation Needed From Tiaknight

Please confirm:

1. Whether `GetNewOrders` plus `GetOrder` is the recommended flow for WIMS.
2. Whether `GetNewOrders` can return all paid orders before manual status changes, or only a queue of new orders.
3. Whether another method exists to fetch orders already moved to `Processing Order`.
4. The full field list/variations available in the v6 order XML, especially:
   - summary
   - personalization / personalisation
   - order status
   - payment status
   - courier / delivery service
   - sample/design fields
5. Whether a WSDL URL or updated SOAP API document is available.

## Current Limitation Seen By WIMS

WIMS only receives orders that Tiaknight returns from `GetNewOrders`.
If an order is not returned by that method, WIMS cannot import or inspect that order unless Tiaknight provides another API method or field variation for it.

For orders returned by `GetNewOrders`, WIMS can now call `GetOrder` to fetch richer v6 detail including personalisation.
