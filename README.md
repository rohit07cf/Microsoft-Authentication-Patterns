# Microsoft-Authentication-Patterns

Implementation of various authentication patterns using the MSAL authentication library.

## Authorization Code Flow POC

A minimal FastAPI application that demonstrates the OAuth 2.0 Authorization Code flow using [MSAL for Python](https://github.com/AzureAD/microsoft-authentication-library-for-python).

### Prerequisites

- Python 3.12+
- An Azure AD App Registration with:
  - A **client secret** created under *Certificates & secrets*
  - A **redirect URI** of `http://localhost:8000/callback` added under *Authentication > Web*
  - **User.Read** API permission granted

### Setup

1. Copy the example env file and fill in your Azure AD values:

   ```
   cp .env.example .env
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Run the app:

   ```
   uvicorn app:app --reload
   ```

4. Open http://localhost:8000 in your browser and click **Sign in with Microsoft**.

### Running with Docker

```
docker build -t msal-auth-code-poc .
docker run --env-file .env -p 8000:8000 msal-auth-code-poc
```

### How it works

1. User visits `/` and clicks the sign-in button.
2. `GET /login` uses MSAL's `initiate_auth_code_flow()` to build an authorization URL and redirects the user to Azure AD.
3. After the user authenticates, Azure AD redirects to `GET /callback` with an authorization code.
4. `acquire_token_by_auth_code_flow()` exchanges the code for tokens (ID token + access token).
5. The ID token claims are stored in a server-side session and the user is redirected back to `/` where their profile info is displayed.
