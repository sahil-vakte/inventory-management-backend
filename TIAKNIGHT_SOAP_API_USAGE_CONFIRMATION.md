# Tiaknight SOAP API Usage Confirmation

Date: 2026-07-10

WIMS is currently integrated with Tiaknight using the SOAP API below.

## API Details

- API type: SOAP
- SOAP version used by WIMS: SOAP 1.1
- Endpoint:

```text
https://www.tiaknightfabrics.co.uk/api/soap/service
```

- Operation currently used:

```text
GetNewOrders
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
 xmlns:ser="http://www.tiaknightfabrics.co.uk/api/soap/service">
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

## Confirmation Needed From Tiaknight

Please confirm:

1. Whether `GetNewOrders` is the correct SOAP 1.1 method for WIMS.
2. Whether another method exists to fetch orders by order reference, for example `WEB236342`.
3. Whether another method exists to fetch orders already moved to `Processing Order`.
4. The full field list/variations available in the order XML, especially:
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

