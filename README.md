# Microsoft Authentication Patterns

A hands-on reference for Microsoft identity platform authentication flows using [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python). Each pattern lives in its own folder with a dedicated README, runnable code, and setup instructions.

---

## Repository structure

```
├── auth_code_flow/             # Authorization Code flow (implemented)
├── client_credentials_flow/    # Client Credentials flow (placeholder)
├── obo_flow/                   # On-Behalf-Of flow (placeholder)
├── device_code_flow/           # Device Code flow (placeholder)
└── README.md                   # This file — concepts & overview
```

---

## Authentication Patterns Overview

| Pattern | Folder | Description | User Interaction |
|---|---|---|---|
| **Authorization Code** | [`auth_code_flow/`](auth_code_flow/) | User signs in via browser redirect; app receives a code and exchanges it for tokens. | Yes |
| **Client Credentials** | [`client_credentials_flow/`](client_credentials_flow/) | App authenticates as itself (no user) using its own identity to access resources. | No |
| **On-Behalf-Of (OBO)** | [`obo_flow/`](obo_flow/) | A middle-tier API exchanges a user's access token for a new token to call a downstream API on the user's behalf. | No (user already authenticated) |
| **Device Code** | [`device_code_flow/`](device_code_flow/) | User authenticates on a separate device by entering a code displayed by the app. Useful for input-constrained devices. | Yes |
| **ROPC** | — | App collects username/password directly and sends them to Azure AD. Not recommended — no MFA, no consent prompts. | Yes (credentials only) |

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

## Getting started

Each pattern folder is a self-contained project. Pick the one you want to explore:

| Pattern | Status | Quick start |
|---|---|---|
| [Authorization Code](auth_code_flow/) | Implemented | `cd auth_code_flow && pip install -r requirements.txt && uvicorn app:app --reload` |
| [Client Credentials](client_credentials_flow/) | Placeholder | Coming soon |
| [On-Behalf-Of](obo_flow/) | Placeholder | Coming soon |
| [Device Code](device_code_flow/) | Placeholder | Coming soon |

See each folder's `README.md` for prerequisites, setup, and detailed documentation.
