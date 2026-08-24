from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, ExpenseSplit, Group, Membership
from app.schemas.expenses import ExpenseSortField, ExpenseUpsertRequest, SortDirection, SplitType


class ExpenseNotFoundError(Exception):
    """Raised when an expense does not exist."""


class ExpenseGroupMembershipRequiredError(Exception):
    """Raised when a user is not a member of an expense's group."""


class ExpenseMutationForbiddenError(Exception):
    """Raised when neither the expense creator nor group owner mutates an expense."""


class ExpenseValidationError(Exception):
    """Raised when expense participants or split amounts are invalid."""


@dataclass(frozen=True)
class ExpensePage:
    expenses: list[Expense]
    total: int
    page: int
    page_size: int


def create_expense(
    session: Session,
    group_id: int,
    creator_id: int,
    data: ExpenseUpsertRequest,
) -> Expense:
    """Persist a validated expense and all of its split rows together."""
    _require_group_membership(session, group_id, creator_id)
    split_rows = _build_split_rows(session, group_id, data)
    expense = Expense(
        group_id=group_id,
        created_by=creator_id,
        description=data.description,
        amount=data.amount,
        paid_by=data.paid_by,
        expense_date=data.expense_date,
        split_type=data.split_type.value,
    )
    session.add(expense)

    try:
        session.flush()
        session.add_all(
            ExpenseSplit(expense_id=expense.id, user_id=user_id, amount=amount)
            for user_id, amount in split_rows
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return get_expense(session, expense.id)


def list_group_expenses(
    session: Session,
    group_id: int,
    page: int,
    page_size: int,
    sort_by: ExpenseSortField,
    sort_order: SortDirection,
) -> ExpensePage:
    """Fetch one sorted expense page in SQL, never by slicing loaded rows."""
    sort_column = Expense.expense_date if sort_by == "date" else Expense.amount
    primary_order = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    id_order = Expense.id.asc() if sort_order == "asc" else Expense.id.desc()

    total = int(
        session.scalar(
            select(func.count(Expense.id)).where(Expense.group_id == group_id)
        )
        or 0
    )
    expenses = list(
        session.scalars(
            select(Expense)
            .options(selectinload(Expense.splits))
            .where(Expense.group_id == group_id)
            .order_by(primary_order, id_order)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ExpensePage(expenses=expenses, total=total, page=page, page_size=page_size)


def update_expense(
    session: Session,
    expense_id: int,
    current_user_id: int,
    data: ExpenseUpsertRequest,
) -> Expense:
    """Replace an authorized expense and all split rows atomically."""
    expense = _get_expense_for_member(session, expense_id, current_user_id)
    _require_expense_mutation_permission(session, expense, current_user_id)
    split_rows = _build_split_rows(session, expense.group_id, data)

    try:
        expense.description = data.description
        expense.amount = data.amount
        expense.paid_by = data.paid_by
        expense.expense_date = data.expense_date
        expense.split_type = data.split_type.value
        session.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id))
        session.add_all(
            ExpenseSplit(expense_id=expense.id, user_id=user_id, amount=amount)
            for user_id, amount in split_rows
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return get_expense(session, expense_id)


def delete_expense(session: Session, expense_id: int, current_user_id: int) -> None:
    """Delete an authorized expense and its split rows without touching users."""
    expense = _get_expense_for_member(session, expense_id, current_user_id)
    _require_expense_mutation_permission(session, expense, current_user_id)

    try:
        session.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id))
        session.execute(delete(Expense).where(Expense.id == expense.id))
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_expense(session: Session, expense_id: int) -> Expense:
    expense = session.scalar(
        select(Expense)
        .options(selectinload(Expense.splits))
        .where(Expense.id == expense_id)
        .execution_options(populate_existing=True)
    )
    if expense is None:
        raise ExpenseNotFoundError
    return expense


def _get_expense_for_member(
    session: Session,
    expense_id: int,
    user_id: int,
) -> Expense:
    expense = get_expense(session, expense_id)
    _require_group_membership(session, expense.group_id, user_id)
    return expense


def _require_group_membership(session: Session, group_id: int, user_id: int) -> None:
    membership_id = session.scalar(
        select(Membership.id).where(
            Membership.group_id == group_id,
            Membership.user_id == user_id,
        )
    )
    if membership_id is None:
        raise ExpenseGroupMembershipRequiredError


def _require_expense_mutation_permission(
    session: Session,
    expense: Expense,
    user_id: int,
) -> None:
    group = session.get(Group, expense.group_id)
    if group is None:
        raise ExpenseNotFoundError
    if expense.created_by != user_id and group.owner_id != user_id:
        raise ExpenseMutationForbiddenError


def _build_split_rows(
    session: Session,
    group_id: int,
    data: ExpenseUpsertRequest,
) -> list[tuple[int, int]]:
    _validate_payer_membership(session, group_id, data.paid_by)

    if data.split_type is SplitType.EQUAL:
        user_ids = data.split_user_ids
        _validate_split_memberships(session, group_id, user_ids)
        quotient, remainder = divmod(data.amount, len(user_ids))
        # The first users in request order receive one extra smallest unit each.
        return [
            (user_id, quotient + (1 if index < remainder else 0))
            for index, user_id in enumerate(user_ids)
        ]

    split_rows = [(split.user_id, split.amount) for split in data.splits]
    _validate_split_memberships(session, group_id, [user_id for user_id, _ in split_rows])
    if sum(amount for _, amount in split_rows) != data.amount:
        raise ExpenseValidationError("Custom split amounts must equal the expense amount")
    return split_rows


def _validate_payer_membership(session: Session, group_id: int, payer_id: int) -> None:
    payer_membership = session.scalar(
        select(Membership.id).where(
            Membership.group_id == group_id,
            Membership.user_id == payer_id,
        )
    )
    if payer_membership is None:
        raise ExpenseValidationError("The payer must be a member of this group")


def _validate_split_memberships(
    session: Session,
    group_id: int,
    user_ids: list[int],
) -> None:
    member_ids = set(
        session.scalars(
            select(Membership.user_id).where(
                Membership.group_id == group_id,
                Membership.user_id.in_(user_ids),
            )
        ).all()
    )
    if member_ids != set(user_ids):
        raise ExpenseValidationError("Every split user must be a member of this group")
