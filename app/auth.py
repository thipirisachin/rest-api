import base64
import os
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

_bearer = HTTPBearer(auto_error=False)


def _load_basic_creds() -> set[tuple[str, str]]:
    """Parse BASIC_CREDS=user1:pass1,user2:pass2 into a set of (user, pass) pairs."""
    raw = os.getenv("BASIC_CREDS", "")
    creds = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            username, _, password = entry.partition(":")
            if username and password:
                creds.add((username, password))
    return creds


def _check_basic(request: Request) -> bool:
    """Returns True if the request carries valid Basic credentials."""
    creds = _load_basic_creds()
    if not creds:
        return False
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode()
        username, _, password = decoded.partition(":")
    except Exception:
        return False
    return (username, password) in creds


def require_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    # Basic auth check (only active when BASIC_USER + BASIC_PASS are set)
    if _check_basic(request):
        return

    # Bearer token check
    expected = os.getenv("API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=500, detail="API_TOKEN not configured")
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
