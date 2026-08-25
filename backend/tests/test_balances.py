from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Expense, ExpenseSplit, Group, Membership, Settlement, User
from app.services.balances import (
    SuggestedPayment,
    calculate_group_balances,
    calculate_user_overall_balance,
)


@pytest.fixture
def balance_data() -> tuple[Session, list[int], list[int]]:
    session = SessionLocal()
    user_ids: list[int] = []
    group_ids: list[int] = []
    try:
        yield session, user_ids, group_ids
    finally:
        session.rollback()
        if group_ids:
            expense_ids = select(Expense.id).where(Expense.group_id.in_(group_ids))
            session.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids)))
            session.execute(delete(Expense).where(Expense.group_id.in_(group_ids)))
            session.execute(delete(Settlement).where(Settlement.group_id.in_(group_ids)))
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(user_ids)))
            session.execute(delete(User).where(User.id.in_(user_ids)))
        session.commit()
        session.close()


def make_group(
    session: Session, user_ids: list[int], group_ids: list[int], member_count: int
) -> tuple[int, list[int]]:
    users = [
        User(
            name=f"Balance User {index}",
            email=f"balance-{uuid4().hex}-{index}@example.com",
            password_hash="not-used",
        )
        for index in range(member_count)
    ]
    session.add_all(users)
    session.flush()
    user_ids.extend(user.id for user in users)
    group = Group(name="Balance test group", owner_id=users[0].id)
    session.add(group)
    session.flush()
    group_ids.append(group.id)
    session.add_all(Membership(group_id=group.id, user_id=user.id) for user in users)
    session.commit()
    return group.id, [user.id for user in users]


def add_expense(
    session: Session, group_id: int, payer_id: int, amount: int, splits: dict[int, int]
) -> None:
    expense = Expense(
        group_id=group_id,
        created_by=payer_id,
        description="Test expense",
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


def balances_by_user(group_id: int, session: Session) -> dict[int, int]:
    result = calculate_group_balances(session, group_id)
    return {entry.user_id: entry.net_balance for entry in result.member_balances}


def test_sign_convention_one_payer_and_multiple_split_members(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (payer, first_member, second_member) = make_group(
        session, user_ids, group_ids, 3
    )
    add_expense(
        session,
        group_id,
        payer,
        900,
        {payer: 300, first_member: 300, second_member: 300},
    )
    session.commit()

    # Positive means owed money; negative means owing money.
    assert balances_by_user(group_id, session) == {
        payer: 600,
        first_member: -300,
        second_member: -300,
    }


def test_multiple_expenses_produce_positive_negative_and_zero_balances(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (first, second, third, zero_member) = make_group(
        session, user_ids, group_ids, 4
    )
    add_expense(session, group_id, first, 1_000, {first: 500, second: 500})
    add_expense(session, group_id, second, 600, {first: 200, second: 200, third: 200})
    session.commit()

    assert balances_by_user(group_id, session) == {
        first: 300,
        second: -100,
        third: -200,
        zero_member: 0,
    }


def test_three_way_uneven_split_preserves_integer_paisa_exactly(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (payer, second, third) = make_group(session, user_ids, group_ids, 3)
    add_expense(session, group_id, payer, 1_001, {payer: 1, second: 333, third: 667})
    session.commit()

    assert balances_by_user(group_id, session) == {
        payer: 1_000,
        second: -333,
        third: -667,
    }


def test_multiple_settlements_reduce_balances_to_zero(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (creditor, first_debtor, second_debtor) = make_group(
        session, user_ids, group_ids, 3
    )
    add_expense(
        session,
        group_id,
        creditor,
        300,
        {creditor: 0, first_debtor: 100, second_debtor: 200},
    )
    session.add_all(
        [
            Settlement(
                group_id=group_id,
                from_user_id=first_debtor,
                to_user_id=creditor,
                amount=100,
            ),
            Settlement(
                group_id=group_id,
                from_user_id=second_debtor,
                to_user_id=creditor,
                amount=200,
            ),
        ]
    )
    session.commit()

    result = calculate_group_balances(session, group_id)
    assert balances_by_user(group_id, session) == {
        creditor: 0,
        first_debtor: 0,
        second_debtor: 0,
    }
    assert result.suggested_payments == ()


def test_simplified_debts_match_multiple_creditors_and_debtors_exactly(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (first_creditor, second_creditor, first_debtor, second_debtor) = make_group(
        session, user_ids, group_ids, 4
    )
    add_expense(
        session,
        group_id,
        first_creditor,
        100,
        {first_debtor: 60, second_debtor: 40},
    )
    add_expense(session, group_id, second_creditor, 30, {first_creditor: 30})
    session.commit()

    result = calculate_group_balances(session, group_id)
    assert result.suggested_payments == (
        SuggestedPayment(first_debtor, first_creditor, 60),
        SuggestedPayment(second_debtor, first_creditor, 10),
        SuggestedPayment(second_debtor, second_creditor, 30),
    )
    payments_total = sum(payment.amount for payment in result.suggested_payments)
    total_debt = -sum(
        balance.net_balance
        for balance in result.member_balances
        if balance.net_balance < 0
    )
    total_credit = sum(
        balance.net_balance
        for balance in result.member_balances
        if balance.net_balance > 0
    )
    assert payments_total == total_debt == total_credit == 100


def test_overall_balance_uses_the_same_sign_convention_across_groups(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    first_group, (user, first_other) = make_group(session, user_ids, group_ids, 2)
    second_group, (second_group_user, second_other) = make_group(
        session, user_ids, group_ids, 2
    )
    # Add the first group's user to the second group, then use that same user there.
    session.add(Membership(group_id=second_group, user_id=user))
    session.commit()
    add_expense(session, first_group, user, 100, {first_other: 100})
    add_expense(session, second_group, second_other, 250, {user: 250})
    session.commit()

    overall = calculate_user_overall_balance(session, user)
    assert overall.total_owed_to_user == 100
    assert overall.total_user_owes == 250
    assert overall.net_balance == -150
    assert second_group_user != user


def test_group_with_no_expenses_returns_every_member_at_zero(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, members = make_group(session, user_ids, group_ids, 3)

    result = calculate_group_balances(session, group_id)
    assert balances_by_user(group_id, session) == {member_id: 0 for member_id in members}
    assert result.suggested_payments == ()


def test_balance_calculations_do_not_write_to_the_database(
    balance_data: tuple[Session, list[int], list[int]],
) -> None:
    session, user_ids, group_ids = balance_data
    group_id, (payer, debtor) = make_group(session, user_ids, group_ids, 2)
    add_expense(session, group_id, payer, 10, {debtor: 10})
    session.commit()

    calculate_group_balances(session, group_id)
    calculate_user_overall_balance(session, payer)

    assert not session.new
    assert not session.dirty
    assert not session.deleted
