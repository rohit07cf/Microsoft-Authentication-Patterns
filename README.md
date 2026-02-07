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

### Key implementation details

- **MSAL `ConfidentialClientApplication`** handles all OAuth complexity — token requests, PKCE, nonce validation.
- **`initiate_auth_code_flow()`** generates the authorization URL with the correct `state`, `nonce`, and `code_challenge` parameters.
- **`acquire_token_by_auth_code_flow()`** validates the response, exchanges the authorization code, and returns the ID token claims and access token.
- **Session management** uses a signed cookie (via `itsdangerous`) pointing to server-side state. A production app should use Redis or a database-backed session store.
