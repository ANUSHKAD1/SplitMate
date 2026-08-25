from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import Activity, Expense, ExpenseSplit, Group, Membership, Settlement, User


client = TestClient(app)


@dataclass(frozen=True)
class ActivityUser:
    id: int
    email: str
    token: str


@pytest.fixture
def user_factory() -> Callable[[str], ActivityUser]:
    created_user_ids: list[int] = []

    def create_user(name: str = "Activity User") -> ActivityUser:
        with SessionLocal() as session:
            user = User(
                name=name,
                email=f"activity-{uuid4().hex}@example.com",
                password_hash="not-used",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return ActivityUser(user.id, user.email, create_access_token(user.id))

    yield create_user

    with SessionLocal() as session:
        group_ids = list(
            session.scalars(
                select(Group.id).where(Group.owner_id.in_(created_user_ids))
            ).all()
        )
        if group_ids:
            expense_ids = select(Expense.id).where(Expense.group_id.in_(group_ids))
            session.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids)))
            session.execute(delete(Expense).where(Expense.group_id.in_(group_ids)))
            session.execute(delete(Settlement).where(Settlement.group_id.in_(group_ids)))
            session.execute(delete(Activity).where(Activity.group_id.in_(group_ids)))
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if created_user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(created_user_ids)))
            session.execute(delete(User).where(User.id.in_(created_user_ids)))
        session.commit()


def auth_headers(user: ActivityUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: ActivityUser) -> int:
    response = client.post(
        "/groups", json={"name": "Activity test group"}, headers=auth_headers(owner)
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def add_member(owner: ActivityUser, group_id: int, member: ActivityUser) -> None:
    response = client.post(
        f"/groups/{group_id}/members",
        json={"email": member.email},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201


def expense_payload(owner_id: int, amount: int = 100) -> dict[str, object]:
    return {
        "description": "Lunch",
        "amount": amount,
        "paid_by": owner_id,
        "expense_date": "2026-08-20",
        "split_type": "equal",
        "split_user_ids": [owner_id],
    }


def list_activity(owner: ActivityUser, group_id: int, suffix: str = ""):
    return client.get(f"/groups/{group_id}/activity{suffix}", headers=auth_headers(owner))


def test_expense_add_edit_and_delete_each_create_activities(
    user_factory: Callable[[str], ActivityUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)
    create_response = client.post(
        f"/groups/{group_id}/expenses",
        json=expense_payload(owner.id),
        headers=auth_headers(owner),
    )
    assert create_response.status_code == 201
    expense_id = create_response.json()["id"]

    edit_response = client.put(
        f"/expenses/{expense_id}",
        json={**expense_payload(owner.id), "description": "Updated lunch"},
        headers=auth_headers(owner),
    )
    assert edit_response.status_code == 200
    delete_response = client.delete(f"/expenses/{expense_id}", headers=auth_headers(owner))
    assert delete_response.status_code == 204

    activity_response = list_activity(owner, group_id)
    assert activity_response.status_code == 200
    assert [item["event_type"] for item in activity_response.json()["items"]] == [
        "expense_deleted",
        "expense_edited",
        "expense_added",
    ]


def test_member_add_and_remove_create_activities(
    user_factory: Callable[[str], ActivityUser],
) -> None:
    owner = user_factory("Owner")
    member = user_factory("New Member")
    group_id = create_group(owner)

    add_member(owner, group_id, member)
    remove_response = client.delete(
        f"/groups/{group_id}/members/{member.id}", headers=auth_headers(owner)
    )
    assert remove_response.status_code == 204

    activities = list_activity(owner, group_id).json()["items"]
    assert [item["event_type"] for item in activities] == [
        "member_removed",
        "member_added",
    ]
    assert all(item["user_id"] == owner.id for item in activities)


def test_settlement_creates_activity(user_factory: Callable[[str], ActivityUser]) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    expense = client.post(
        f"/groups/{group_id}/expenses",
        json={
            **expense_payload(creditor.id),
            "split_user_ids": [debtor.id],
        },
        headers=auth_headers(creditor),
    )
    assert expense.status_code == 201

    settlement = client.post(
        f"/groups/{group_id}/settlements",
        json={"to_user_id": creditor.id, "amount": 100},
        headers=auth_headers(debtor),
    )
    assert settlement.status_code == 201

    latest_activity = list_activity(creditor, group_id).json()["items"][0]
    assert latest_activity["event_type"] == "settlement_recorded"
    assert latest_activity["user_id"] == debtor.id


def test_non_member_cannot_view_group_activity(
    user_factory: Callable[[str], ActivityUser],
) -> None:
    owner = user_factory("Owner")
    outsider = user_factory("Outsider")
    group_id = create_group(owner)

    response = list_activity(outsider, group_id)

    assert response.status_code == 403
    assert response.json() == {"detail": "You are not a member of this group"}


def test_activity_is_group_scoped_newest_first_and_paginated(
    user_factory: Callable[[str], ActivityUser],
) -> None:
    owner = user_factory("Owner")
    first_member = user_factory("First")
    second_member = user_factory("Second")
    third_member = user_factory("Third")
    other_group_member = user_factory("Other")
    group_id = create_group(owner)
    other_group_id = create_group(owner)
    add_member(owner, group_id, first_member)
    add_member(owner, group_id, second_member)
    add_member(owner, group_id, third_member)
    add_member(owner, other_group_id, other_group_member)

    first_page = list_activity(owner, group_id, "?page=1&page_size=2")
    second_page = list_activity(owner, group_id, "?page=2&page_size=2")

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["total_pages"] == 2
    assert [item["id"] for item in first_page.json()["items"]] == sorted(
        [item["id"] for item in first_page.json()["items"]], reverse=True
    )
    assert len(second_page.json()["items"]) == 1
    assert {item["group_id"] for item in first_page.json()["items"]} == {group_id}
    assert {item["group_id"] for item in second_page.json()["items"]} == {group_id}


def test_failed_expense_creation_does_not_create_an_activity(
    user_factory: Callable[[str], ActivityUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)

    response = client.post(
        f"/groups/{group_id}/expenses",
        json={
            "description": "Invalid",
            "amount": 100,
            "paid_by": owner.id,
            "expense_date": "2026-08-20",
            "split_type": "custom",
            "splits": [{"user_id": owner.id, "amount": 99}],
        },
        headers=auth_headers(owner),
    )

    assert response.status_code == 422
    activity_response = list_activity(owner, group_id)
    assert activity_response.json()["total"] == 0
