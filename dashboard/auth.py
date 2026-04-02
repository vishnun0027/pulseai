"""
dashboard/auth.py
Authentication helpers and auth routes for the dashboard API.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from pydantic import BaseModel, Field

from storage.db import execute, fetch_one

ACCESS_TOKEN_COOKIE = "pulseai_session"
ACCESS_TOKEN_TTL_HOURS = int(os.environ.get("AUTH_TOKEN_TTL_HOURS", "12"))
JWT_ALGORITHM = "HS256"
JWT_SECRET = os.environ.get("JWT_SECRET", "pulseai-dev-secret-change-me")
COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "false").lower() == "true"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class AuthUser(BaseModel):
    id: int
    username: str
    role: str


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except (UnknownHashError, ValueError):
        return False


def create_access_token(user: AuthUser) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "uid": user.id,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_TTL_HOURS * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE, path="/")


async def get_user_by_username(username: str) -> Optional[AuthUser]:
    row = await fetch_one(
        """
        SELECT id, username, role
        FROM users
        WHERE username = $1
        """,
        username,
    )
    if not row:
        return None
    return AuthUser(id=row["id"], username=row["username"], role=row["role"])


async def get_authenticated_user(
    token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
) -> AuthUser:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        uid = payload.get("uid")
        role = payload.get("role")
        if not username or uid is None or not role:
            raise ValueError("Missing token claims")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from None

    user = await get_user_by_username(username)
    if not user or user.id != uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(current_user: AuthUser = Depends(get_authenticated_user)) -> AuthUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@auth_router.get("/me")
async def get_current_user(current_user: AuthUser = Depends(get_authenticated_user)):
    return {"authenticated": True, "user": current_user.model_dump()}


@auth_router.get("/bootstrap-status")
async def bootstrap_status():
    row = await fetch_one("SELECT COUNT(*) AS total FROM users")
    total = row["total"] if row else 0
    return {"bootstrap_required": total == 0}


@auth_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    response: Response,
    token: Optional[str] = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
):
    existing_count = await fetch_one("SELECT COUNT(*) AS total FROM users")
    is_first_user = (existing_count["total"] if existing_count else 0) == 0

    if not is_first_user:
        current_user = await get_authenticated_user(token)
        if current_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    existing_user = await fetch_one(
        "SELECT id FROM users WHERE username = $1",
        user_in.username.strip().lower(),
    )
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    role = "admin" if is_first_user else "analyst"
    username = user_in.username.strip().lower()
    row = await fetch_one(
        """
        INSERT INTO users (username, password_hash, role)
        VALUES ($1, $2, $3)
        RETURNING id, username, role
        """,
        username,
        hash_password(user_in.password),
        role,
    )
    await execute(
        "UPDATE users SET last_login_at = NOW() WHERE id = $1",
        row["id"],
    )

    auth_user = AuthUser(id=row["id"], username=row["username"], role=row["role"])
    token = create_access_token(auth_user)
    _set_auth_cookie(response, token)
    return {
        "status": "created",
        "user": auth_user.model_dump(),
        "bootstrap": is_first_user,
    }


@auth_router.post("/login")
async def login(user_in: UserLogin, response: Response):
    username = user_in.username.strip().lower()
    row = await fetch_one(
        """
        SELECT id, username, password_hash, role
        FROM users
        WHERE username = $1
        """,
        username,
    )
    if not row or not verify_password(user_in.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    auth_user = AuthUser(id=row["id"], username=row["username"], role=row["role"])
    token = create_access_token(auth_user)
    _set_auth_cookie(response, token)
    await execute("UPDATE users SET last_login_at = NOW() WHERE id = $1", row["id"])
    return {"status": "ok", "user": auth_user.model_dump()}


@auth_router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"status": "ok"}
