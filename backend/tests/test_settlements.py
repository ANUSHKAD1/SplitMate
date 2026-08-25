from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import Expense, ExpenseSplit, Group, Membership, Settlement, User
from app.services.balances import calculate_group_balances


client = TestClient(app)


@dataclass(frozen=True)
class SettlementUser:
    id: int
    email: str
    token: str


@pytest.fixture
def user_factory() -> Callable[[str], SettlementUser]:
    created_user_ids: list[int] = []

    def create_user(name: str = "Settlement User") -> SettlementUser:
        with SessionLocal() as session:
            user = User(
                name=name,
                email=f"settlement-{uuid4().hex}@example.com",
                password_hash="not-used",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return SettlementUser(user.id, user.email, create_access_token(user.id))

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
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if created_user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(created_user_ids)))
            session.execute(delete(User).where(User.id.in_(created_user_ids)))
        session.commit()


def auth_headers(user: SettlementUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: SettlementUser) -> int:
    response = client.post(
        "/groups", json={"name": "Settlement test group"}, headers=auth_headers(owner)
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def add_member(owner: SettlementUser, group_id: int, member: SettlementUser) -> None:
    response = client.post(
        f"/groups/{group_id}/members",
        json={"email": member.email},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201


def create_debt(
    group_id: int, creditor_id: int, debtor_id: int, amount: int = 100
) -> None:
    with SessionLocal() as session:
        expense = Expense(
            group_id=group_id,
            created_by=creditor_id,
            description="Shared dinner",
            amount=amount,
            paid_by=creditor_id,
            expense_date=date.today(),
        )
        session.add(expense)
        session.flush()
        session.add(ExpenseSplit(expense_id=expense.id, user_id=debtor_id, amount=amount))
        session.commit()


def settle(
    payer: SettlementUser, group_id: int, recipient_id: int, amount: int
):
    return client.post(
        f"/groups/{group_id}/settlements",
        json={"to_user_id": recipient_id, "amount": amount},
        headers=auth_headers(payer),
    )


def test_valid_settlement_succeeds_and_changes_canonical_balances(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(debtor, group_id, creditor.id, 60)

    assert response.status_code == 201
    assert response.json()["from_user"]["id"] == debtor.id
    assert response.json()["to_user"]["id"] == creditor.id
    assert response.json()["amount"] == 60
    with SessionLocal() as session:
        balances = calculate_group_balances(session, group_id)
    assert balances.balance_for(creditor.id) == 40
    assert balances.balance_for(debtor.id) == -40


@pytest.mark.parametrize("amount", [0, -1])
def test_settlement_amount_must_be_positive(
    user_factory: Callable[[str], SettlementUser], amount: int
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(debtor, group_id, creditor.id, amount)

    assert response.status_code == 422


def test_settlement_users_must_be_different(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)

    response = settle(owner, group_id, owner.id, 1)

    assert response.status_code == 422
    assert response.json() == {"detail": "Settlement users must be different"}


def test_non_member_cannot_create_a_settlement(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    outsider = user_factory("Outsider")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(outsider, group_id, creditor.id, 10)

    assert response.status_code == 403
    assert response.json() == {"detail": "You are not a member of this group"}


def test_settlement_target_must_be_a_group_member(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    outsider = user_factory("Outsider")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(debtor, group_id, outsider.id, 10)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Settlement participants must both be members of this group"
    }


def test_cannot_settle_without_a_balance_relationship(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    uninvolved_member = user_factory("Uninvolved")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    add_member(creditor, group_id, uninvolved_member)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(debtor, group_id, uninvolved_member.id, 10)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "The users do not have a settleable balance relationship"
    }


def test_cannot_settle_more_than_currently_owed(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    response = settle(debtor, group_id, creditor.id, 101)

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Settlement amount exceeds the amount currently owed"
    }


def test_valid_settlement_can_bring_balances_to_zero(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_debt(group_id, creditor.id, debtor.id)

    assert settle(debtor, group_id, creditor.id, 100).status_code == 201
    with SessionLocal() as session:
        balances = calculate_group_balances(session, group_id)
    assert balances.balance_for(creditor.id) == 0
    assert balances.balance_for(debtor.id) == 0


def test_settlement_list_is_group_scoped_and_newest_first(
    user_factory: Callable[[str], SettlementUser],
) -> None:
    creditor = user_factory("Creditor")
    first_debtor = user_factory("First Debtor")
    second_debtor = user_factory("Second Debtor")
    first_group_id = create_group(creditor)
    add_member(creditor, first_group_id, first_debtor)
    create_debt(first_group_id, creditor.id, first_debtor.id)
    assert settle(first_debtor, first_group_id, creditor.id, 40).status_code == 201
    assert settle(first_debtor, first_group_id, creditor.id, 30).status_code == 201

    second_group_id = create_group(creditor)
    add_member(creditor, second_group_id, second_debtor)
    create_debt(second_group_id, creditor.id, second_debtor.id)
    assert settle(second_debtor, second_group_id, creditor.id, 10).status_code == 201

    response = client.get(
        f"/groups/{first_group_id}/settlements", headers=auth_headers(creditor)
    )

    assert response.status_code == 200
    assert [item["amount"] for item in response.json()] == [30, 40]
    assert {item["group_id"] for item in response.json()} == {first_group_id}
