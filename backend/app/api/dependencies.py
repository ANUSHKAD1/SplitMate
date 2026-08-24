from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import JWT_ALGORITHM
from app.db.session import get_db_session
from app.models import Membership, User


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Resolve the authenticated user from a valid Bearer access token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _invalid_access_token_exception()

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError as error:
        raise _invalid_access_token_exception() from error

    if payload.get("type") != "access":
        raise _invalid_access_token_exception()

    user_id = _parse_user_id(payload)
    if user_id is None:
        raise _invalid_access_token_exception()

    user = session.get(User, user_id)
    if user is None:
        raise _invalid_access_token_exception()

    return user


def require_group_member(
    group_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> User:
    """Require the current user to be a member of the requested group."""
    membership_id = session.scalar(
        select(Membership.id).where(
            Membership.group_id == group_id,
            Membership.user_id == current_user.id,
        )
    )
    if membership_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this group",
        )

    return current_user


def _parse_user_id(payload: dict[str, Any]) -> int | None:
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdecimal():
        return None

    user_id = int(subject)
    return user_id if user_id > 0 else None


def _invalid_access_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
