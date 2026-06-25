# TODO 2026-06-25 - Royal Mail OAuth Setup

## Details Received

- App/site callback URL: `https://www.wims.cloud/auth/royalmail/callback`
- Royal Mail OAuth callback path: `/auth/royalmail/callback`
- Royal Mail client ID: `6c5ddb35ba81d232b375948a49751b7c`
- Royal Mail client secret: store only in `.env` or server secret manager. Do not commit plaintext secret.

## Environment Variables To Add

Local/server `.env`:

```env
ROYAL_MAIL_CLIENT_ID=6c5ddb35ba81d232b375948a49751b7c
ROYAL_MAIL_CLIENT_SECRET=<store real client secret here>
ROYAL_MAIL_OAUTH_CALLBACK_URL=https://www.wims.cloud/auth/royalmail/callback
ROYAL_MAIL_OAUTH_CALLBACK_PATH=/auth/royalmail/callback
ROYAL_MAIL_OAUTH_AUTHORIZATION_URL=https://auth.parcel.royalmail.com/oauth2/authorize
ROYAL_MAIL_OAUTH_TOKEN_URL=https://auth.parcel.royalmail.com/oauth2/token
ROYAL_MAIL_OAUTH_SCOPE=
```

## Implementation TODO

- [x] Add Royal Mail OAuth settings to Django settings from environment variables.
- [x] Add Royal Mail OAuth start/login endpoint.
- [x] Add callback endpoint for `https://www.wims.cloud/auth/royalmail/callback`.
- [x] Exchange callback `code` for access/refresh token.
- [x] Store tokens securely.
- [x] Add token refresh logic.
- [x] Add token status/config endpoint.
- [x] Update Royal Mail booking client to use OAuth token if Royal Mail requires OAuth for this app.
- [x] Keep existing API-key based flow available until OAuth flow is confirmed.
- [x] Add Postman requests for:
  - OAuth config/status
  - OAuth start URL
  - callback documentation/request notes
  - Royal Mail shipment booking
- [x] Add tests for:
  - missing client ID/client secret
  - callback without code
  - token exchange success
  - token exchange failure
  - booking blocked when not connected

## Safety Notes

- Never commit the Royal Mail client secret.
- Never print client secret or tokens in logs.
- Mask secrets in config/status API responses.
- Store production values on the server environment, not in code.

## Expected Flow

1. Admin opens Royal Mail connect/start endpoint in WIMS.
2. User signs into Royal Mail and authorizes WIMS.
3. Royal Mail redirects to:

   ```text
   https://www.wims.cloud/auth/royalmail/callback?code=...
   ```

4. WIMS backend exchanges `code` for token.
5. WIMS stores token securely.
6. WIMS can book Royal Mail shipments for completed orders.

## Open Questions

- [ ] Confirm Royal Mail OAuth authorization URL with Royal Mail after first real connect attempt.
- [ ] Confirm Royal Mail token URL with Royal Mail after first real connect attempt.
- [ ] Confirm required OAuth scopes.
- [ ] Confirm whether Royal Mail shipment booking uses OAuth token, API key, or both in production.
- [ ] Confirm token expiry and refresh behavior from live response.
