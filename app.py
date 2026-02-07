import os
import uuid

import msal
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

# Secret key used to sign the session cookie
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-in-production")
serializer = URLSafeSerializer(SESSION_SECRET)

app = FastAPI(title="MSAL Auth Code Flow POC")
templates = Jinja2Templates(directory="templates")

# In-memory store keyed by session id – maps to MSAL flow state and user info.
# A production app would use a real session store (Redis, database, etc.).
_sessions: dict[str, dict] = {}


def _build_msal_app() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
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

    # Store user claims from the ID token.
    session["user"] = result.get("id_token_claims", {})
    session.pop("flow", None)

    return RedirectResponse("/")


@app.get("/logout")
async def logout(request: Request):
    """Clear the local session and redirect to Azure AD logout."""
    session_id = _get_session_id(request)
    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response = RedirectResponse("/")
    response.delete_cookie("session_id")
    return response
