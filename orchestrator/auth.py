"""JWT authentication helpers for the AgenticHealthMCP API."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-a-long-random-string")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

_bearer = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = None,
) -> dict:
    """
    FastAPI dependency — validates Bearer token from Authorization header or
    ?token= query param (needed for EventSource which can't set headers).
    Returns {"user_id": str, "username": str}.
    """
    raw = None
    if credentials:
        raw = credentials.credentials
    elif token:
        raw = token

    if not raw:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(raw)
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": user_id, "username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
