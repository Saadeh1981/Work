from fastapi import Header, HTTPException, Request
import os

PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/healthz",
    "/version",
    "/ops/env-check",
    "/metadata/catalog",
    "/metadata/library",
}

def _is_valid(api_key_header: str | None) -> bool:
    current = os.getenv("PUBLIC_API_KEY")
    next_key = os.getenv("PUBLIC_API_KEY_NEXT")
    return api_key_header is not None and api_key_header in {current, next_key}

async def require_api_key_except_public(
    request: Request,
    x_api_key: str | None = Header(None, alias="x-api-key"),
):
    # 1. Always bypass auth in local
    if os.getenv("APP_ENV", "local") == "local":
        return

    # 2. Allow public paths
    path = request.url.path.rstrip("/") or "/"
    if path in PUBLIC_PATHS:
        return

    # 3. Enforce API key
    if not _is_valid(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid API Key")

