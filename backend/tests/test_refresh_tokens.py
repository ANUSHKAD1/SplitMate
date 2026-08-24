from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.security import JWT_ALGORITHM, hash_refresh_token
from app.db.session import SessionLocal
from app.main import app
from app.models import RefreshToken, User


client = TestClient(app)


@pytest.fixture
def registered_credentials() -> dict[str, str]:
    email = f"refresh-test-{uuid4().hex}@example.com"
    password = "SecurePass1!"
    registration_response = client.post(
        "/auth/register",
        json={"name": "Asha Patel", "email": email, "password": password},
    )
    assert registration_response.status_code == 201

    yield {"email": email, "password": password}

    with SessionLocal() as session:
        session.execute(delete(User).where(User.email == email))
        session.commit()


def login(credentials: dict[str, str]) -> dict[str, str]:
    response = client.post("/auth/login", json=credentials)
    assert response.status_code == 200
    return response.json()


def refresh(refresh_token: str) -> object:
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


def test_login_returns_a_raw_refresh_token_but_stores_only_its_hash(
    registered_credentials: dict[str, str],
) -> None:
    tokens = login(registered_credentials)

    assert set(tokens) == {"access_token", "refresh_token", "token_type"}
    with SessionLocal() as session:
        stored_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
            )
        )

    assert stored_token is not None
    assert stored_token.token_hash != tokens["refresh_token"]
    assert stored_token.revoked_at is None


def test_valid_refresh_returns_new_access_and_refresh_tokens(
    registered_credentials: dict[str, str],
) -> None:
    initial_tokens = login(registered_credentials)
    response = refresh(initial_tokens["refresh_token"])

    assert response.status_code == 200
    refreshed_tokens = response.json()
    assert isinstance(refreshed_tokens["access_token"], str)
    assert refreshed_tokens["refresh_token"] != initial_tokens["refresh_token"]
    assert refreshed_tokens["token_type"] == "bearer"
    claims = jwt.decode(
        refreshed_tokens["access_token"],
        settings.jwt_secret_key,
        algorithms=[JWT_ALGORITHM],
    )
    assert claims["type"] == "access"

    with SessionLocal() as session:
        old_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(initial_tokens["refresh_token"])
            )
        )
        new_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refreshed_tokens["refresh_token"])
            )
        )

    assert old_token is not None and old_token.revoked_at is not None
    assert new_token is not None and new_token.revoked_at is None
    assert (new_token.expires_at - new_token.created_at).total_seconds() == pytest.approx(
        7 * 24 * 60 * 60,
        abs=5,
    )


def test_old_refresh_token_is_rejected_after_rotation(
    registered_credentials: dict[str, str],
) -> None:
    initial_tokens = login(registered_credentials)
    assert refresh(initial_tokens["refresh_token"]).status_code == 200

    response = refresh(initial_tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


def test_expired_refresh_token_is_rejected(
    registered_credentials: dict[str, str],
) -> None:
    tokens = login(registered_credentials)
    with SessionLocal() as session:
        refresh_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
            )
        )
        assert refresh_token is not None
        refresh_token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()

    response = refresh(tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


def test_revoked_refresh_token_is_rejected(
    registered_credentials: dict[str, str],
) -> None:
    tokens = login(registered_credentials)
    with SessionLocal() as session:
        refresh_token = session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
            )
        )
        assert refresh_token is not None
        refresh_token.revoked_at = datetime.now(timezone.utc)
        session.commit()

    response = refresh(tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired refresh token"}


def test_logout_revokes_refresh_token_idempotently(
    registered_credentials: dict[str, str],
) -> None:
    tokens = login(registered_credentials)

    first_logout = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    second_logout = client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    refresh_response = refresh(tokens["refresh_token"])

    assert first_logout.status_code == 204
    assert second_logout.status_code == 204
    assert refresh_response.status_code == 401


def test_invalid_or_missing_refresh_token_is_rejected() -> None:
    invalid_response = refresh("not-a-valid-refresh-token")
    missing_response = client.post("/auth/refresh", json={})

    assert invalid_response.status_code == 401
    assert invalid_response.json() == {"detail": "Invalid or expired refresh token"}
    assert missing_response.status_code == 401
    assert missing_response.json() == {"detail": "Invalid or expired refresh token"}
