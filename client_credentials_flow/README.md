# Client Credentials Flow

> **Status:** Not yet implemented.

The Client Credentials flow allows an application to authenticate **as itself** (no user involved) using its own client ID and secret (or certificate). It is used for daemon services, background jobs, and any scenario where the app acts with **application permissions** rather than delegated permissions.

## When to use

- Backend services, cron jobs, or pipelines that run without a signed-in user.
- Accessing resources scoped to the entire tenant (e.g. read all users, process mailboxes).

## Key MSAL API

```python
app = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
```
