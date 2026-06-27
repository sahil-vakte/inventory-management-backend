# Royal Mail Integration Options

We have two possible ways to connect WIMS with Royal Mail. Please confirm which option you want to use.

## Option 1 - Click & Drop API

This is the current recommended option for the existing WIMS flow.

Used for:

- Sending completed WIMS orders to Royal Mail Click & Drop
- Creating Royal Mail shipments/orders
- Updating WIMS order status to `Shipped`
- Saving tracking/reference details if Royal Mail returns them

Required from client:

```text
Royal Mail Click & Drop API authorisation key
```

Where to get it:

```text
Royal Mail Click & Drop > Settings > Integrations > Click & Drop API
```

Official sites:

- Click & Drop login: https://auth.parcel.royalmail.com/account/login
- Click & Drop API guide: https://help.parcel.royalmail.com/hc/en-gb/articles/360011462338-Integrating-with-the-Click-Drop-API

Backend setting:

```env
ROYAL_MAIL_API_KEY=<click-drop-api-authorisation-key>
```

Notes:

- This does not use client ID/client secret.
- This matches the current backend endpoint:

```text
https://api.parcel.royalmail.com/api/v1/Orders
```

## Option 2 - Royal Mail Developer Portal API

This uses the Royal Mail developer portal credentials.

Used for:

- Royal Mail APIs subscribed through `developer.royalmail.net`
- Possible APIs include Shipping API, Tracking API, Local Collect API, etc.

Required from client:

```text
Royal Mail API product name
Client ID
Client Secret
Sandbox/live endpoint
API documentation or subscribed API details
```

Official sites:

- Royal Mail API Developer Portal: https://developer.royalmail.net/
- Developer Portal getting started: https://developer.royalmail.net/start
- Royal Mail APIs overview: https://www.royalmail.com/business/tools-services/apis

Notes:

- This is not the same as Click & Drop API.
- It may require different endpoints, request payloads, and response handling.
- Backend changes will be needed after confirming the exact Royal Mail API product.

## Recommendation

For the current requirement, use:

```text
Option 1 - Click & Drop API
```

Because WIMS already has the Click & Drop order booking flow implemented.

If the client wants to use `client ID` and `client secret`, then they need to confirm the exact Royal Mail Developer Portal API product they subscribed to.

## Decision Needed

Please confirm one:

```text
1. Use Click & Drop API authorisation key
2. Use Royal Mail Developer Portal API with client ID/client secret
```
