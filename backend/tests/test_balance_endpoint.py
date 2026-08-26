from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select

from app.core.security import create_access_token
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import Expense, ExpenseSplit, Group, Membership, Settlement, User
from app.schemas.money import paise_to_rupees
from app.services.balances import calculate_group_balances


client = TestClient(app)


@dataclass(frozen=True)
class BalanceUser:
    id: int
    email: str
    name: str
    token: str


@pytest.fixture
def user_factory() -> Callable[[str], BalanceUser]:
    created_user_ids: list[int] = []

    def create_user(name: str) -> BalanceUser:
        with SessionLocal() as session:
            user = User(
                name=name,
                email=f"balance-endpoint-{uuid4().hex}@example.com",
                password_hash="not-used",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return BalanceUser(
                id=user.id,
                email=user.email,
                name=user.name,
                token=create_access_token(user.id),
            )

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


def auth_headers(user: BalanceUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: BalanceUser, members: list[BalanceUser]) -> int:
    with SessionLocal() as session:
        group = Group(name="Balance endpoint test group", owner_id=owner.id)
        session.add(group)
        session.flush()
        session.add_all(
            Membership(group_id=group.id, user_id=member.id)
            for member in [owner, *members]
        )
        session.commit()
        return group.id


def add_expense(
    group_id: int,
    payer_id: int,
    amount: int,
    splits: dict[int, int],
) -> None:
    with SessionLocal() as session:
        expense = Expense(
            group_id=group_id,
            created_by=payer_id,
            description="Balance endpoint test expense",
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


def get_balances(user: BalanceUser, group_id: int):
    return client.get(f"/groups/{group_id}/balances", headers=auth_headers(user))


def test_group_member_receives_canonical_balances_and_debt_suggestions(
    user_factory: Callable[[str], BalanceUser],
) -> None:
    first_creditor = user_factory("First Creditor")
    second_creditor = user_factory("Second Creditor")
    first_debtor = user_factory("First Debtor")
    second_debtor = user_factory("Second Debtor")
    group_id = create_group(
        first_creditor,
        [second_creditor, first_debtor, second_debtor],
    )
    add_expense(
        group_id,
        first_creditor.id,
        25_000,
        {first_debtor.id: 25_000},
    )
    add_expense(
        group_id,
        second_creditor.id,
        25_050,
        {second_debtor.id: 25_050},
    )

    with SessionLocal() as session:
        canonical = calculate_group_balances(session, group_id)

    assert {balance.user_id: balance.net_balance for balance in canonical.member_balances} == {
        first_creditor.id: 25_000,
        second_creditor.id: 25_050,
        first_debtor.id: -25_000,
        second_debtor.id: -25_050,
    }
    response = get_balances(first_creditor, group_id)

    assert response.status_code == 200
    body = response.json()
    balances_by_user = {item["user_id"]: item["net_balance"] for item in body["balances"]}
    assert balances_by_user[first_creditor.id] == "250.00"
    assert balances_by_user[first_debtor.id] == "-250.00"
    assert balances_by_user[second_creditor.id] == "250.50"
    assert balances_by_user[second_debtor.id] == "-250.50"
    assert [debt["amount"] for debt in body["debts"]] == ["250.00", "250.50"]

    names = {
        user.id: user.name
        for user in [first_creditor, second_creditor, first_debtor, second_debtor]
    }
    assert body["balances"] == [
        {
            "user_id": balance.user_id,
            "name": names[balance.user_id],
            "net_balance": paise_to_rupees(balance.net_balance),
        }
        for balance in canonical.member_balances
    ]
    assert body["debts"] == [
        {
            "from_user_id": payment.from_user_id,
            "from_user_name": names[payment.from_user_id],
            "to_user_id": payment.to_user_id,
            "to_user_name": names[payment.to_user_id],
            "amount": paise_to_rupees(payment.amount),
        }
        for payment in canonical.suggested_payments
    ]


def test_non_member_cannot_retrieve_group_balances(
    user_factory: Callable[[str], BalanceUser],
) -> None:
    owner = user_factory("Owner")
    outsider = user_factory("Outsider")
    group_id = create_group(owner, [])

    response = get_balances(outsider, group_id)

    assert response.status_code == 403
    assert response.json() == {"detail": "You are not a member of this group"}


def test_unauthenticated_request_is_rejected(
    user_factory: Callable[[str], BalanceUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner, [])

    response = client.get(f"/groups/{group_id}/balances")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired access token"}


def test_balance_endpoint_performs_no_database_writes(
    user_factory: Callable[[str], BalanceUser],
) -> None:
    owner = user_factory("Owner")
    debtor = user_factory("Debtor")
    group_id = create_group(owner, [debtor])
    add_expense(group_id, owner.id, 100, {debtor.id: 100})
    write_statements: list[str] = []

    def record_statement(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        del conn, cursor, parameters, context, executemany
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "MERGE")):
            write_statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        response = get_balances(owner, group_id)
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    assert response.status_code == 200
    assert write_statements == []

