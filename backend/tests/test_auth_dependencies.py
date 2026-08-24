from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.dependencies import get_current_user, require_group_member
from app.core.config import settings
from app.core.security import JWT_ALGORITHM, create_access_token
from app.db.session import SessionLocal
from app.models import Group, Membership, User


dependency_app = FastAPI()


@dependency_app.get("/protected")
def protected_route(
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, int]:
    return {"user_id": current_user.id}


@dependency_app.get("/groups/{group_id}/protected")
def protected_group_route(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
) -> dict[str, int]:
    return {"group_id": group_id, "user_id": current_user.id}


client = TestClient(dependency_app)


@pytest.fixture
def authenticated_user() -> dict[str, int | str]:
    email = f"auth-dependency-{uuid4().hex}@example.com"
    with SessionLocal() as session:
        user = User(name="Asha Patel", email=email, password_hash="not-used")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    yield {"id": user_id, "token": create_access_token(user_id)}

    with SessionLocal() as session:
        session.execute(delete(Membership).where(Membership.user_id == user_id))
        session.execute(delete(Group).where(Group.owner_id == user_id))
        session.execute(delete(User).where(User.id == user_id))
        session.commit()


def bearer_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_missing_authorization_header_is_rejected() -> None:
    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_malformed_access_token_is_rejected() -> None:
    response = client.get("/protected", headers=bearer_headers("not-a-jwt"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_expired_access_token_is_rejected(authenticated_user: dict[str, int | str]) -> None:
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": str(authenticated_user["id"]),
            "iat": now - timedelta(minutes=16),
            "exp": now - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )

    response = client.get("/protected", headers=bearer_headers(expired_token))

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_valid_access_token_resolves_current_user(
    authenticated_user: dict[str, int | str],
) -> None:
    response = client.get(
        "/protected",
        headers=bearer_headers(str(authenticated_user["token"])),
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": authenticated_user["id"]}


def test_access_token_for_nonexistent_user_is_rejected() -> None:
    response = client.get(
        "/protected",
        headers=bearer_headers(create_access_token(999_999_999)),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_group_member_authorization_succeeds(
    authenticated_user: dict[str, int | str],
) -> None:
    user_id = int(authenticated_user["id"])
    with SessionLocal() as session:
        group = Group(name="Weekend trip", owner_id=user_id)
        session.add(group)
        session.flush()
        session.add(Membership(group_id=group.id, user_id=user_id))
        session.commit()
        group_id = group.id

    response = client.get(
        f"/groups/{group_id}/protected",
        headers=bearer_headers(str(authenticated_user["token"])),
    )

    assert response.status_code == 200
    assert response.json() == {"group_id": group_id, "user_id": user_id}


def test_non_member_is_forbidden(authenticated_user: dict[str, int | str]) -> None:
    owner_email = f"group-owner-{uuid4().hex}@example.com"
    with SessionLocal() as session:
        owner = User(name="Group Owner", email=owner_email, password_hash="not-used")
        session.add(owner)
        session.flush()
        group = Group(name="Weekend trip", owner_id=owner.id)
        session.add(group)
        session.commit()
        owner_id = owner.id
        group_id = group.id

    try:
        response = client.get(
            f"/groups/{group_id}/protected",
            headers=bearer_headers(str(authenticated_user["token"])),
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "You are not a member of this group"}
    finally:
        with SessionLocal() as session:
            session.execute(delete(Group).where(Group.id == group_id))
            session.execute(delete(User).where(User.id == owner_id))
            session.commit()
