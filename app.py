import os
import uuid

import msal
import requests as http_requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer

load_dotenv()

CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["User.Read"]
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0/me"

# Secret key used to sign the session cookie
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
serializer = URLSafeSerializer(SESSION_SECRET)

app = FastAPI(title="MSAL Auth Code Flow POC")
templates = Jinja2Templates(directory="templates")

# In-memory store keyed by session id – maps to MSAL flow state and user info.
# A production app would use a real session store (Redis, database, etc.).
_sessions: dict[str, dict] = {}

# Shared MSAL token cache – keeps access and refresh tokens across requests.
# In production, use a distributed cache (Redis, database) so tokens survive
# restarts and work across multiple app instances.
_token_cache = msal.SerializableTokenCache()


def _build_msal_app() -> msal.ConfidentialClientApplication:
    """Build an MSAL client that shares a single token cache."""
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
        token_cache=_token_cache,
    )


def _get_session_id(request: Request) -> str | None:
    cookie = request.cookies.get("session_id")
    if cookie is None:
        return None
    try:
        return serializer.loads(cookie)
    except Exception:
        return None


# ---------- Routes ----------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the home / login page."""
    session_id = _get_session_id(request)
    user = _sessions.get(session_id, {}).get("user") if session_id else None
    return templates.TemplateResponse(
        "index.html", {"request": request, "user": user}
    )


@app.get("/login")
async def login():
    """Initiate the Authorization Code flow by redirecting to Azure AD."""
    cca = _build_msal_app()
    flow = cca.initiate_auth_code_flow(
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    # Persist the flow so we can complete it in the callback.
    session_id = uuid.uuid4().hex
    _sessions[session_id] = {"flow": flow}

    response = RedirectResponse(flow["auth_uri"])
    response.set_cookie(
        key="session_id",
        value=serializer.dumps(session_id),
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/callback")
async def callback(request: Request):
    """Handle the redirect from Azure AD and exchange the code for tokens."""
    session_id = _get_session_id(request)
    session = _sessions.get(session_id) if session_id else None

    if session is None or "flow" not in session:
        return RedirectResponse("/")

    cca = _build_msal_app()
    result = cca.acquire_token_by_auth_code_flow(
        session["flow"],
        dict(request.query_params),
    )

    if "error" in result:
        return HTMLResponse(
            f"<h3>Authentication failed</h3>"
            f"<p>{result.get('error')}: {result.get('error_description')}</p>"
            f'<a href="/">Back</a>',
            status_code=400,
        )

    # Store user claims and the home_account_id for silent token lookups.
    session["user"] = result.get("id_token_claims", {})
    session["home_account_id"] = result.get("id_token_claims", {}).get("oid")
    session.pop("flow", None)

    return RedirectResponse("/")


@app.get("/call-graph")
async def call_graph(request: Request):
    """Silently acquire an access token and call Microsoft Graph /me."""
    session_id = _get_session_id(request)
    session = _sessions.get(session_id) if session_id else None

    if session is None or "home_account_id" not in session:
        return RedirectResponse("/")

    cca = _build_msal_app()

    # Look up the account from the MSAL cache using the stored identifier.
    accounts = cca.get_accounts()
    account = next(
        (a for a in accounts if a.get("local_account_id") == session["home_account_id"]),
        None,
    )

    if account is None:
        # Account not in cache – need a fresh interactive sign-in.
        return RedirectResponse("/login")

    # Attempt a silent token acquisition.
    # MSAL will return the cached access token if still valid, or use the
    # refresh token to obtain a new one – no user interaction required.
    result = cca.acquire_token_silent(scopes=SCOPES, account=account)

    if not result or "access_token" not in result:
        # Silent refresh failed (e.g. refresh token expired/revoked).
        # Fall back to interactive sign-in.
        return RedirectResponse("/login")

    token_source = result.get("token_source", "unknown")

    # Call the Microsoft Graph API with the access token.
    graph_response = http_requests.get(
        GRAPH_ENDPOINT,
        headers={"Authorization": f"Bearer {result['access_token']}"},
        timeout=10,
    )

    if graph_response.ok:
        profile = graph_response.json()
    else:
        profile = {
            "error": graph_response.status_code,
            "message": graph_response.text,
        }

    return templates.TemplateResponse(
        "graph_result.html",
        {
            "request": request,
            "profile": profile,
            "token_source": token_source,
        },
    )


@app.get("/logout")
async def logout(request: Request):
    """Clear the local session and redirect to Azure AD logout."""
    session_id = _get_session_id(request)
    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response = RedirectResponse("/")
    response.delete_cookie("session_id")
    return response
