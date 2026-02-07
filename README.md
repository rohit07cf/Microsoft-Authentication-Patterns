# Microsoft Authentication Patterns

A hands-on reference for Microsoft identity platform authentication flows using [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python).

---

## Authentication Patterns Overview

| Pattern | Description | User Interaction |
|---|---|---|
| **Authorization Code** | User signs in via browser redirect; app receives a code and exchanges it for tokens. | Yes |
| **Client Credentials** | App authenticates as itself (no user) using its own identity to access resources. | No |
| **On-Behalf-Of (OBO)** | A middle-tier API exchanges a user's access token for a new token to call a downstream API on the user's behalf. | No (user already authenticated) |
| **Device Code** | User authenticates on a separate device by entering a code displayed by the app. Useful for input-constrained devices. | Yes |
| **ROPC (Resource Owner Password Credentials)** | App collects username/password directly and sends them to Azure AD. Not recommended — no MFA, no consent prompts. | Yes (credentials only) |

---

## Application Permissions vs Delegated Permissions

| | Delegated Permissions | Application Permissions |
|---|---|---|
| **Who is acting** | The app acts **on behalf of a signed-in user** | The app acts **as itself**, with no user present |
| **Consent** | User (or admin) grants consent at sign-in | Admin pre-approves in the Azure portal |
| **Token type** | User access token (contains user claims) | App-only access token (no user context) |
| **Use case** | Read *this user's* profile, send mail *as this user* | Read *all users'* profiles, process background jobs |
| **Typical flows** | Authorization Code, Device Code, OBO | Client Credentials |

**Key takeaway:** If you need to call an API *as a user*, you need a delegated permission and a user access token. If your app runs unattended (daemon, pipeline), you need application permissions and the Client Credentials flow.

---

## How to Obtain Delegated Permissions

A delegated permission requires a **user access token**. The way you get one depends on whether the user can interact with a browser.

### Interactive (user present)

| Flow | When to use |
|---|---|
| **Authorization Code** | Web apps and APIs where the user can sign in through a browser redirect. **Recommended for most scenarios.** |
| **Device Code** | CLI tools, IoT devices, or environments without a browser. |

### Non-Interactive (no user prompt)

| Flow | When to use |
|---|---|
| **On-Behalf-Of (OBO)** | A middle-tier API already has the user's token and needs to call another API downstream. |
| **ROPC** | Legacy migration only. Sends raw credentials — bypasses MFA and consent. Avoid in new projects. |
| **Silent / Cache** | MSAL's `acquire_token_silent()` returns a cached or refreshed token without prompting the user again. Used after any initial interactive flow. |

---

## POC: Authorization Code Flow

The Authorization Code flow is the **recommended interactive pattern** for obtaining user consent and delegated tokens. This POC implements it end-to-end with FastAPI and MSAL.

### How it works

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

### Project structure

```
├── app.py              # FastAPI app — /login, /callback, /logout endpoints
├── templates/
│   └── index.html      # Login page / user profile display
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container image
├── .env.example        # Configuration template
└── README.md
```

### Prerequisites

- Python 3.12+
- An **Azure AD App Registration** with:
  - A **client secret** under *Certificates & secrets*
  - A **redirect URI** `http://localhost:8000/callback` under *Authentication > Web*
  - **User.Read** delegated permission under *API permissions*

### Quick start

```bash
cp .env.example .env          # fill in AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
pip install -r requirements.txt
uvicorn app:app --reload
```

Open http://localhost:8000 and click **Sign in with Microsoft**.

### Docker

```bash
docker build -t msal-auth-code-poc .
docker run --env-file .env -p 8000:8000 msal-auth-code-poc
```

### Token lifetimes

After a successful Authorization Code flow, Azure AD returns the following tokens:

| Token | Default Lifetime | Purpose |
|---|---|---|
| **Access token** | **60–90 minutes** (typically ~1 hour) | Short-lived credential sent with each API request. Grants access to the scopes the user consented to. |
| **Refresh token** | **90 days** (sliding window, extended on use up to a max of 90 days of inactivity) | Long-lived credential stored server-side. Used to obtain new access tokens without user interaction. |
| **ID token** | **~1 hour** | Contains user profile claims. Used for session establishment, not for API calls. |

> These are the Microsoft identity platform defaults. Admins can customize lifetimes via [Token Lifetime Policies](https://learn.microsoft.com/en-us/entra/identity-platform/configurable-token-lifetimes) or Conditional Access.

### Silent token refresh

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

### Key implementation details

- **MSAL `ConfidentialClientApplication`** handles all OAuth complexity — token requests, PKCE, nonce validation.
- **`initiate_auth_code_flow()`** generates the authorization URL with the correct `state`, `nonce`, and `code_challenge` parameters.
- **`acquire_token_by_auth_code_flow()`** validates the response, exchanges the authorization code, and returns the ID token claims and access token.
- **`acquire_token_silent()`** retrieves cached tokens or silently refreshes them using the refresh token — no user interaction required.
- **Session management** uses a signed cookie (via `itsdangerous`) pointing to server-side state. A production app should use Redis or a database-backed session store.
