from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.core.security import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM
from app.db.session import SessionLocal
from app.main import app
from app.models import User


client = TestClient(app)


@pytest.fixture
def registered_credentials() -> dict[str, str]:
    email = f"login-test-{uuid4().hex}@example.com"
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


def login(credentials: dict[str, str]):
    return client.post("/auth/login", json=credentials)


def test_valid_login_returns_access_token(
    registered_credentials: dict[str, str],
) -> None:
    response = login(registered_credentials)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert isinstance(response.json()["access_token"], str)


def test_wrong_password_is_rejected(
    registered_credentials: dict[str, str],
) -> None:
    response = login({**registered_credentials, "password": "WrongPass1!"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_unknown_email_is_rejected_like_wrong_password() -> None:
    response = login(
        {
            "email": f"unknown-login-{uuid4().hex}@example.com",
            "password": "WrongPass1!",
        }
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


def test_access_token_is_a_valid_jwt_with_access_claims(
    registered_credentials: dict[str, str],
) -> None:
    response = login(registered_credentials)

    assert response.status_code == 200
    claims = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret_key,
        algorithms=[JWT_ALGORITHM],
    )

    assert {"sub", "iat", "exp", "type"}.issubset(claims)
    assert claims["type"] == "access"
    assert claims["sub"].isdigit()
    assert claims["exp"] - claims["iat"] == pytest.approx(
        ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        abs=5,
    )


def test_login_response_does_not_include_password_data(
    registered_credentials: dict[str, str],
) -> None:
    response = login(registered_credentials)

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
