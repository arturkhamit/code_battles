import jwt
from fastapi import Depends, HTTPException, Query, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer_scheme = HTTPBearer()


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.PyJWTError:
        raise ValueError("Invalid token")

    if payload.get("token_type") != "access":
        raise ValueError("Not an access token")

    # simplejwt puts user_id into the token as a string; everything downstream wants an int
    try:
        payload["user_id"] = int(payload["user_id"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid token") from None

    return payload


def _identity(payload: dict) -> dict:
    return {"user_id": payload["user_id"], "username": payload.get("username", "")}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return _identity(payload)


async def get_current_user_ws(token: str = Query(...)) -> dict:
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return _identity(payload)
