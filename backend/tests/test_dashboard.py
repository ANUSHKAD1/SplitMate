from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import Activity, Expense, ExpenseSplit, Group, Membership, Settlement, User


client = TestClient(app)


@dataclass(frozen=True)
class DashboardUser:
    id: int
    token: str


@pytest.fixture
def dashboard_data() -> tuple[Callable[[str], DashboardUser], list[int], list[int]]:
    user_ids: list[int] = []
    group_ids: list[int] = []

    def make_user(name: str) -> DashboardUser:
        with SessionLocal() as session:
            user = User(
                name=name,
                email=f"dashboard-{uuid4().hex}@example.com",
                password_hash="not-used",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            user_ids.append(user.id)
            return DashboardUser(user.id, create_access_token(user.id))

    yield make_user, user_ids, group_ids

    with SessionLocal() as session:
        if group_ids:
            expense_ids = [
                expense_id
                for expense_id in session.scalars(
                    __import__("sqlalchemy").select(Expense.id).where(Expense.group_id.in_(group_ids))
                ).all()
            ]
            if expense_ids:
                session.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids)))
            session.execute(delete(Expense).where(Expense.group_id.in_(group_ids)))
            session.execute(delete(Settlement).where(Settlement.group_id.in_(group_ids)))
            session.execute(delete(Activity).where(Activity.group_id.in_(group_ids)))
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(user_ids)))
            session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()


def headers(user: DashboardUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def make_group(session, owner_id: int, member_ids: list[int], name: str) -> int:
    group = Group(name=name, owner_id=owner_id)
    session.add(group)
    session.flush()
    session.add_all(Membership(group_id=group.id, user_id=user_id) for user_id in member_ids)
    session.commit()
    return group.id


def add_expense(session, group_id: int, payer_id: int, splits: dict[int, int]) -> None:
    amount = sum(splits.values())
    expense = Expense(
        group_id=group_id,
        created_by=payer_id,
        description="Dashboard test expense",
        amount=amount,
        paid_by=payer_id,
        expense_date=date.today(),
    )
    session.add(expense)
    session.flush()
    session.add_all(
        ExpenseSplit(expense_id=expense.id, user_id=user_id, amount=split_amount)
        for user_id, split_amount in splits.items()
    )
    session.commit()


def add_activity(session, group_id: int, user_id: int, message: str) -> None:
    session.add(
        Activity(
            group_id=group_id,
            user_id=user_id,
            event_type="expense_added",
            message=message,
        )
    )
    session.commit()


def test_dashboard_is_authenticated_and_reconciles_multiple_group_balances(
    dashboard_data: tuple[Callable[[str], DashboardUser], list[int], list[int]],
) -> None:
    make_user, user_ids, group_ids = dashboard_data
    dashboard_user = make_user("Dashboard User")
    other_user = make_user("Other User")
    unrelated_user = make_user("Unrelated User")
    with SessionLocal() as session:
        positive_group = make_group(
            session, dashboard_user.id, [dashboard_user.id, other_user.id], "Owed to me"
        )
        negative_group = make_group(
            session, other_user.id, [other_user.id, dashboard_user.id], "I owe this"
        )
        zero_group = make_group(session, dashboard_user.id, [dashboard_user.id], "Settled")
        unrelated_group = make_group(
            session, unrelated_user.id, [unrelated_user.id], "Private"
        )
        group_ids.extend([positive_group, negative_group, zero_group, unrelated_group])
        add_expense(session, positive_group, dashboard_user.id, {other_user.id: 100})
        add_expense(session, negative_group, other_user.id, {dashboard_user.id: 250})
        add_expense(session, zero_group, dashboard_user.id, {dashboard_user.id: 20})
        add_expense(session, unrelated_group, unrelated_user.id, {unrelated_user.id: 999})

    response = client.get("/dashboard", headers=headers(dashboard_user))

    assert response.status_code == 200
    body = response.json()
    assert body["total_owed_to_user"] == 100
    assert body["total_user_owes"] == 250
    assert body["net_balance"] == -150
    assert body["net_balance"] == body["total_owed_to_user"] - body["total_user_owes"]
    assert body["group_count"] == 3
    assert body["group_where_user_owes_most"] == {
        "group_id": negative_group,
        "group_name": "I owe this",
        "amount_owed": 250,
    }


def test_unauthenticated_dashboard_is_rejected() -> None:
    response = client.get("/dashboard")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_dashboard_returns_null_largest_debt_when_user_owes_nothing(
    dashboard_data: tuple[Callable[[str], DashboardUser], list[int], list[int]],
) -> None:
    make_user, user_ids, group_ids = dashboard_data
    dashboard_user = make_user("Dashboard User")
    other_user = make_user("Other User")
    with SessionLocal() as session:
        group_id = make_group(
            session, dashboard_user.id, [dashboard_user.id, other_user.id], "Credit only"
        )
        group_ids.append(group_id)
        add_expense(session, group_id, dashboard_user.id, {other_user.id: 80})

    response = client.get("/dashboard", headers=headers(dashboard_user))

    assert response.status_code == 200
    assert response.json()["total_owed_to_user"] == 80
    assert response.json()["total_user_owes"] == 0
    assert response.json()["net_balance"] == 80
    assert response.json()["group_where_user_owes_most"] is None


def test_dashboard_recent_activity_is_membership_scoped_newest_first_and_paginated(
    dashboard_data: tuple[Callable[[str], DashboardUser], list[int], list[int]],
) -> None:
    make_user, user_ids, group_ids = dashboard_data
    dashboard_user = make_user("Dashboard User")
    other_user = make_user("Other User")
    unrelated_user = make_user("Unrelated User")
    with SessionLocal() as session:
        first_group = make_group(
            session, dashboard_user.id, [dashboard_user.id], "First group"
        )
        second_group = make_group(
            session, other_user.id, [other_user.id, dashboard_user.id], "Second group"
        )
        unrelated_group = make_group(
            session, unrelated_user.id, [unrelated_user.id], "Unrelated group"
        )
        group_ids.extend([first_group, second_group, unrelated_group])
        add_activity(session, first_group, dashboard_user.id, "oldest visible")
        add_activity(session, second_group, other_user.id, "middle visible")
        add_activity(session, first_group, dashboard_user.id, "newest visible")
        add_activity(session, unrelated_group, unrelated_user.id, "private activity")

    first_page = client.get("/dashboard?page=1&page_size=2", headers=headers(dashboard_user))
    second_page = client.get("/dashboard?page=2&page_size=2", headers=headers(dashboard_user))

    assert first_page.status_code == 200
    first_body = first_page.json()
    assert first_body["recent_activity_total"] == 3
    assert first_body["recent_activity_total_pages"] == 2
    assert [item["message"] for item in first_body["recent_activity"]] == [
        "newest visible",
        "middle visible",
    ]
    assert [item["message"] for item in second_page.json()["recent_activity"]] == [
        "oldest visible"
    ]
    assert {item["group_id"] for item in first_body["recent_activity"]} <= {
        first_group,
        second_group,
    }
