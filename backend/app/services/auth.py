from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_refresh_token_expiration,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.auth import LoginRequest, RegistrationRequest


class DuplicateEmailError(Exception):
    """Raised when a user attempts to register an existing email address."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials cannot be authenticated."""


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is missing, invalid, revoked, or expired."""


@dataclass(frozen=True)
class AuthenticationTokens:
    access_token: str
    refresh_token: str


def register_user(session: Session, registration: RegistrationRequest) -> User:
    existing_user = session.scalar(
        select(User.id).where(User.email == registration.email)
    )
    if existing_user is not None:
        raise DuplicateEmailError

    user = User(
        name=registration.name,
        email=registration.email,
        password_hash=hash_password(registration.password),
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateEmailError from error

    session.refresh(user)
    return user


def authenticate_user(session: Session, credentials: LoginRequest) -> AuthenticationTokens:
    user = session.scalar(select(User).where(User.email == credentials.email))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise InvalidCredentialsError

    refresh_token = _create_refresh_token(session, user.id)
    session.commit()
    return AuthenticationTokens(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


def refresh_user_tokens(
    session: Session, raw_refresh_token: str | None
) -> AuthenticationTokens:
    if not raw_refresh_token:
        raise InvalidRefreshTokenError

    refresh_token = session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw_refresh_token))
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if (
        refresh_token is None
        or refresh_token.revoked_at is not None
        or refresh_token.expires_at <= now
    ):
        raise InvalidRefreshTokenError

    user = session.get(User, refresh_token.user_id)
    if user is None:
        raise InvalidRefreshTokenError

    refresh_token.revoked_at = now
    new_refresh_token = _create_refresh_token(session, user.id)
    session.commit()
    return AuthenticationTokens(
        access_token=create_access_token(user.id),
        refresh_token=new_refresh_token,
    )


def revoke_refresh_token(session: Session, raw_refresh_token: str | None) -> None:
    """Revoke a refresh token when present; safe to repeat for logout idempotency."""
    if not raw_refresh_token:
        return

    refresh_token = session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(raw_refresh_token)
        )
    )
    if refresh_token is not None and refresh_token.revoked_at is None:
        refresh_token.revoked_at = datetime.now(timezone.utc)
        session.commit()


def _create_refresh_token(session: Session, user_id: int) -> str:
    """Generate a raw token while persisting only its hash and lifecycle metadata."""
    raw_refresh_token = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=get_refresh_token_expiration(),
        )
    )
    return raw_refresh_token
