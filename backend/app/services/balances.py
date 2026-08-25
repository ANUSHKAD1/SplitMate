"""Read-only, canonical balance calculations for SplitMate.

All amounts are integer smallest currency units (for example, paisa).  A positive
net balance means a member is owed money; a negative balance means the member
owes money.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseSplit, Membership, Settlement


@dataclass(frozen=True)
class MemberBalance:
    """One group member's signed balance in smallest currency units."""

    user_id: int
    net_balance: int


@dataclass(frozen=True)
class SuggestedPayment:
    """A read-only recommendation for a debtor to pay a creditor."""

    from_user_id: int
    to_user_id: int
    amount: int


@dataclass(frozen=True)
class GroupBalanceResult:
    """Canonical balances and debt-simplification suggestions for one group."""

    group_id: int
    member_balances: tuple[MemberBalance, ...]
    suggested_payments: tuple[SuggestedPayment, ...]

    def balance_for(self, user_id: int) -> int:
        """Return a member's signed balance, or raise KeyError if not a member."""
        for balance in self.member_balances:
            if balance.user_id == user_id:
                return balance.net_balance
        raise KeyError(user_id)


@dataclass(frozen=True)
class UserOverallBalance:
    """A user's aggregate position across every group they currently belong to."""

    user_id: int
    total_owed_to_user: int
    total_user_owes: int
    net_balance: int


class BalanceInvariantError(ValueError):
    """Raised when persisted financial rows cannot be reconciled into payments."""


def calculate_group_balances(session: Session, group_id: int) -> GroupBalanceResult:
    """Calculate every current member's balances and simplified payments.

    This function deliberately performs queries only: it does not add, flush,
    commit, roll back, or otherwise write through ``session``.  Settlements use
    the persisted model's payment direction: ``from_user_id`` paid
    ``to_user_id``.  Therefore a payment increases the payer's signed balance
    (reducing what they owe) and decreases the recipient's signed balance
    (reducing what they are owed).
    """
    member_ids = list(
        session.scalars(
            select(Membership.user_id)
            .where(Membership.group_id == group_id)
            .order_by(Membership.user_id)
        ).all()
    )
    balances = {user_id: 0 for user_id in member_ids}

    for paid_by, amount in session.execute(
        select(Expense.paid_by, Expense.amount).where(Expense.group_id == group_id)
    ):
        _apply_balance_change(balances, paid_by, int(amount))

    for user_id, amount in session.execute(
        select(ExpenseSplit.user_id, ExpenseSplit.amount)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id)
    ):
        _apply_balance_change(balances, user_id, -int(amount))

    for from_user_id, to_user_id, amount in session.execute(
        select(Settlement.from_user_id, Settlement.to_user_id, Settlement.amount).where(
            Settlement.group_id == group_id
        )
    ):
        payment_amount = int(amount)
        _apply_balance_change(balances, from_user_id, payment_amount)
        _apply_balance_change(balances, to_user_id, -payment_amount)

    member_balances = tuple(
        MemberBalance(user_id=user_id, net_balance=balances[user_id])
        for user_id in member_ids
    )
    return GroupBalanceResult(
        group_id=group_id,
        member_balances=member_balances,
        suggested_payments=_simplify_debts(member_balances),
    )


def calculate_user_overall_balance(session: Session, user_id: int) -> UserOverallBalance:
    """Return a user's signed aggregate across their current group memberships."""
    group_ids = list(
        session.scalars(
            select(Membership.group_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.group_id)
        ).all()
    )
    group_balances = [
        calculate_group_balances(session, group_id).balance_for(user_id)
        for group_id in group_ids
    ]
    total_owed_to_user = sum(balance for balance in group_balances if balance > 0)
    total_user_owes = -sum(balance for balance in group_balances if balance < 0)
    return UserOverallBalance(
        user_id=user_id,
        total_owed_to_user=total_owed_to_user,
        total_user_owes=total_user_owes,
        net_balance=sum(group_balances),
    )


def _apply_balance_change(balances: dict[int, int], user_id: int, amount: int) -> None:
    """Apply a validated group financial row without silently dropping a user."""
    if user_id not in balances:
        raise BalanceInvariantError(
            f"Financial record references user {user_id}, who is not a current group member"
        )
    balances[user_id] += amount


def _simplify_debts(
    member_balances: tuple[MemberBalance, ...],
) -> tuple[SuggestedPayment, ...]:
    """Greedily match debtors to creditors while preserving exact integer totals."""
    creditors = [
        [balance.user_id, balance.net_balance]
        for balance in member_balances
        if balance.net_balance > 0
    ]
    debtors = [
        [balance.user_id, -balance.net_balance]
        for balance in member_balances
        if balance.net_balance < 0
    ]
    total_credit = sum(amount for _, amount in creditors)
    total_debt = sum(amount for _, amount in debtors)
    if total_credit != total_debt:
        raise BalanceInvariantError(
            "Group balances do not reconcile: total credits and debts differ"
        )

    payments: list[SuggestedPayment] = []
    creditor_index = 0
    debtor_index = 0
    while creditor_index < len(creditors) and debtor_index < len(debtors):
        creditor_id, credit_remaining = creditors[creditor_index]
        debtor_id, debt_remaining = debtors[debtor_index]
        amount = min(credit_remaining, debt_remaining)
        payments.append(
            SuggestedPayment(
                from_user_id=debtor_id,
                to_user_id=creditor_id,
                amount=amount,
            )
        )
        creditors[creditor_index][1] -= amount
        debtors[debtor_index][1] -= amount
        if creditors[creditor_index][1] == 0:
            creditor_index += 1
        if debtors[debtor_index][1] == 0:
            debtor_index += 1

    return tuple(payments)
