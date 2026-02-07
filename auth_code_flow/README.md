# Authorization Code Flow

The Authorization Code flow is the **recommended interactive pattern** for obtaining user consent and delegated tokens. This POC implements it end-to-end with FastAPI and MSAL.

## How it works

```
Browser                        FastAPI App                     Azure AD
  │                                │                               │
  │  1. GET /login                 │                               │
  │ ──────────────────────────────>│                               │
  │                                │  2. initiate_auth_code_flow() │
  │                                │ ─────────────────────────────>│
  │  3. 302 Redirect to Azure AD   │                               │
  │ <──────────────────────────────│                               │
  │                                                                │
  │  4. User signs in + consents                                   │
  │ ──────────────────────────────────────────────────────────────>│
  │                                                                │
  │  5. 302 Redirect to /callback?code=...                         │
  │ <──────────────────────────────────────────────────────────────│
  │                                │                               │
  │  6. GET /callback?code=...     │                               │
  │ ──────────────────────────────>│                               │
  │                                │  7. Exchange code for tokens  │
  │                                │ ─────────────────────────────>│
  │                                │  8. ID token + access token   │
  │                                │ <─────────────────────────────│
  │  9. Set session, redirect /    │                               │
  │ <──────────────────────────────│                               │
```

## Project structure

```
auth_code_flow/
├── app.py              # FastAPI app — /login, /callback, /call-graph, /logout
├── templates/
│   ├── index.html      # Login page / user profile display
│   └── graph_result.html  # Graph API result with token source badge
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container image
├── .dockerignore
├── .env.example        # Configuration template
└── README.md
```

## Prerequisites

- Python 3.12+
- An **Azure AD App Registration** with:
  - A **client secret** under *Certificates & secrets*
  - A **redirect URI** `http://localhost:8000/callback` under *Authentication > Web*
  - **User.Read** delegated permission under *API permissions*

## Quick start

```bash
cd auth_code_flow
cp .env.example .env          # fill in AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://localhost:8000 and click **Sign in with Microsoft**.

## Docker

```bash
cd auth_code_flow
docker build -t msal-auth-code-poc .
docker run --env-file .env -p 8000:8000 msal-auth-code-poc
```

## Token lifetimes

After a successful Authorization Code flow, Azure AD returns the following tokens:

| Token | Default Lifetime | Purpose |
|---|---|---|
| **Access token** | **60–90 minutes** (typically ~1 hour) | Short-lived credential sent with each API request. Grants access to the scopes the user consented to. |
| **Refresh token** | **90 days** (sliding window, extended on use up to a max of 90 days of inactivity) | Long-lived credential stored server-side. Used to obtain new access tokens without user interaction. |
| **ID token** | **~1 hour** | Contains user profile claims. Used for session establishment, not for API calls. |

> These are the Microsoft identity platform defaults. Admins can customize lifetimes via [Token Lifetime Policies](https://learn.microsoft.com/en-us/entra/identity-platform/configurable-token-lifetimes) or Conditional Access.

## Silent token refresh

Users should **not** have to sign in every time an access token expires. MSAL handles this automatically:

1. **Initial sign-in** — The Authorization Code flow returns an access token *and* a refresh token. MSAL caches both.
2. **On the next API call** — The app calls `acquire_token_silent()`. MSAL checks its cache:
   - If the access token is still valid, it is returned immediately (no network call).
   - If the access token has expired, MSAL uses the refresh token to request a new access token from Azure AD in the background.
3. **User is never prompted** — This cycle repeats silently for as long as the refresh token is valid (~90 days of activity).
4. **Refresh token expires** — Only when the user has been inactive for 90 days (or the token is revoked by an admin) does MSAL return `None`, signaling the app to trigger a new interactive sign-in.

```
App                              MSAL Cache                     Azure AD
 │                                  │                               │
 │  acquire_token_silent()          │                               │
 │ ────────────────────────────────>│                               │
 │                                  │                               │
 │  Cache hit (token still valid)?  │                               │
 │ <─ YES ── return access token ───│                               │
 │                                  │                               │
 │  Cache miss (token expired)?     │                               │
 │               ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌>│  POST /token (refresh_token) │
 │                                  │ ─────────────────────────────>│
 │                                  │  new access token + refresh   │
 │                                  │ <─────────────────────────────│
 │ <─── return new access token ────│                               │
```

This is why the Authorization Code flow is recommended — a single interactive sign-in gives the app long-lived refresh capability, keeping the user experience seamless.

## Proactive token refresh

Rather than waiting for a request to discover an expired token, this POC runs a **background task** that monitors the MSAL token cache and refreshes access tokens *before* they expire.

**How it works:**

1. On app startup, an `asyncio` background loop begins running every `TOKEN_REFRESH_CHECK_INTERVAL_SECS` (default **60 s**).
2. Each cycle, it deserialises the `SerializableTokenCache`, walks every cached access token, and checks its `expires_on` timestamp.
3. If any token will expire within `TOKEN_REFRESH_BUFFER_SECS` (default **5 minutes**), the task calls `acquire_token_silent(force_refresh=True)` to obtain a fresh access token using the refresh token — no user interaction.
4. When `/call-graph` is hit, `acquire_token_silent()` returns the already-refreshed token instantly from cache (`token_source="cache"`).

```
Background Task                  MSAL Cache                     Azure AD
 │                                  │                               │
 │  [every 60s] check expires_on    │                               │
 │ ────────────────────────────────>│                               │
 │                                  │                               │
 │  Token expires in < 5 min?       │                               │
 │  acquire_token_silent(           │                               │
 │    force_refresh=True)           │                               │
 │ ────────────────────────────────>│  POST /token (refresh_token)  │
 │                                  │ ─────────────────────────────>│
 │                                  │  new access + refresh token   │
 │                                  │ <─────────────────────────────│
 │  Cache updated with fresh token  │                               │
 │ <────────────────────────────────│                               │
 │                                                                  │
 ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 │                                                                  │
App (on user request)            MSAL Cache                         │
 │                                  │                               │
 │  acquire_token_silent()          │                               │
 │ ────────────────────────────────>│                               │
 │ <── instant cache hit ───────────│  (no network call needed)     │
```

| Environment variable | Default | Description |
|---|---|---|
| `TOKEN_REFRESH_BUFFER_SECS` | `300` | Refresh a token when it has fewer than this many seconds left before expiry. |
| `TOKEN_REFRESH_CHECK_INTERVAL_SECS` | `60` | How often (in seconds) the background task scans the cache. |

## Key implementation details

- **MSAL `ConfidentialClientApplication`** handles all OAuth complexity — token requests, PKCE, nonce validation.
- **`initiate_auth_code_flow()`** generates the authorization URL with the correct `state`, `nonce`, and `code_challenge` parameters.
- **`acquire_token_by_auth_code_flow()`** validates the response, exchanges the authorization code, and returns the ID token claims and access token.
- **`acquire_token_silent()`** retrieves cached tokens or silently refreshes them using the refresh token — no user interaction required.
- **Proactive background refresh** deserialises the token cache, checks `expires_on` timestamps, and calls `acquire_token_silent(force_refresh=True)` before tokens expire so every user request gets an instant cache hit.
- **Session management** uses a signed cookie (via `itsdangerous`) pointing to server-side state. A production app should use Redis or a database-backed session store.
