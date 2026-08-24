from uuid import uuid4

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models import User


client = TestClient(app)


@pytest.fixture
def registration_email() -> str:
    email = f"registration-test-{uuid4().hex}@example.com"
    yield email

    with SessionLocal() as session:
        session.execute(delete(User).where(User.email == email))
        session.commit()


def valid_registration_payload(email: str) -> dict[str, str]:
    return {
        "name": "Asha Patel",
        "email": email,
        "password": "SecurePass1!",
    }


def test_valid_registration_succeeds(registration_email: str) -> None:
    response = client.post(
        "/auth/register",
        json=valid_registration_payload(f"  {registration_email.upper()}  "),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Asha Patel"
    assert body["email"] == registration_email
    assert set(body) == {"id", "name", "email", "created_at"}


def test_invalid_email_is_rejected(registration_email: str) -> None:
    payload = valid_registration_payload(registration_email)
    payload["email"] = "not-an-email"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_weak_password_is_rejected(registration_email: str) -> None:
    payload = valid_registration_payload(registration_email)
    payload["password"] = "weakpass"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422
    assert "Password must include" in response.text


def test_duplicate_email_is_rejected(registration_email: str) -> None:
    payload = valid_registration_payload(registration_email)
    first_response = client.post("/auth/register", json=payload)
    duplicate_response = client.post("/auth/register", json=payload)

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "An account with this email already exists"


def test_stored_password_is_a_bcrypt_hash(registration_email: str) -> None:
    plaintext_password = "SecurePass1!"
    payload = valid_registration_payload(registration_email)

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    with SessionLocal() as session:
        password_hash = session.scalar(
            select(User.password_hash).where(User.email == registration_email)
        )

    assert password_hash is not None
    assert password_hash != plaintext_password
    assert password_hash.startswith("$2")
    assert bcrypt.checkpw(plaintext_password.encode("utf-8"), password_hash.encode("utf-8"))
