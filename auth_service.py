import hashlib
import os
from fastapi import Header, HTTPException

AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "false").lower() == "true"


def _token_to_user(token: str) -> str:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"u_{digest[:16]}"


def resolve_user_id(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
):
    if x_user_id:
        return x_user_id.strip()[:64]

    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return _token_to_user(token)

    if AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Provide ****** or X-User-Id"})

    return "anonymous"


def resolve_user_from_headers(headers) -> str:
    x_user_id = headers.get("x-user-id")
    if x_user_id:
        return x_user_id.strip()[:64]
    authorization = headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            return _token_to_user(token)
    if AUTH_REQUIRED:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "Provide ****** or X-User-Id"})
    return "anonymous"
