# On-Behalf-Of (OBO) Flow

> **Status:** Not yet implemented.

The On-Behalf-Of flow allows a middle-tier API that has already received a user's access token to exchange it for a new token scoped to a downstream API. The downstream call is made **on behalf of the original user**, preserving their identity and permissions.

## When to use

- A front-end app calls API-A with a user token. API-A needs to call API-B as that same user.
- Microservice chains where user context must propagate across service boundaries.

## Key MSAL API

```python
app = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
result = app.acquire_token_on_behalf_of(user_assertion=incoming_token, scopes=["api://downstream/.default"])
```
