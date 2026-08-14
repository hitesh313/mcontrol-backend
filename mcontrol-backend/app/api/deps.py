from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.core.security import decode_token
from app.database.supabase_client import get_supabase
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=True)


def get_db() -> Client:
    return get_supabase()


def get_user_repository(db: Annotated[Client, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> dict:
    """Validates the JWT access token and loads the corresponding active user.
    Raises 401 for any invalid/expired/malformed token or deactivated user —
    the identical error for every failure mode avoids leaking which check failed.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise unauthorized
        user_id = payload.get("sub")
        if not user_id:
            raise unauthorized
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise unauthorized

    user = user_repo.get_by_id(user_id)
    if not user or not user.get("is_active"):
        raise unauthorized
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
DbSession = Annotated[Client, Depends(get_db)]
