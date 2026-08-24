from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activity, Expense, ExpenseSplit, Group, Membership, Settlement, User


class GroupNotFoundError(Exception):
    """Raised when a requested group does not exist."""


class GroupOwnerRequiredError(Exception):
    """Raised when a group mutation is attempted by a non-owner."""


class MemberAlreadyExistsError(Exception):
    """Raised when a user is already a member of the group."""


class MemberUserNotFoundError(Exception):
    """Raised when an invitation email has no registered user."""


class GroupMemberNotFoundError(Exception):
    """Raised when the requested user is not a member of the group."""


class CannotRemoveGroupOwnerError(Exception):
    """Raised when attempting to remove a group's owner."""


class MemberHasNonzeroBalanceError(Exception):
    """Raised when a member with unsettled group obligations is removed."""


@dataclass(frozen=True)
class GroupDetails:
    group: Group
    members: list[tuple[Membership, User]]


def create_group(session: Session, owner_id: int, name: str) -> Group:
    """Create a group and its owner's membership in one transaction."""
    group = Group(name=name, owner_id=owner_id)
    session.add(group)

    try:
        session.flush()
        session.add(Membership(group_id=group.id, user_id=owner_id))
        session.commit()
    except Exception:
        session.rollback()
        raise

    session.refresh(group)
    return group


def list_groups_for_user(session: Session, user_id: int) -> list[Group]:
    """Return only groups where the user has a membership record."""
    return list(
        session.scalars(
            select(Group)
            .join(Membership, Membership.group_id == Group.id)
            .where(Membership.user_id == user_id)
            .order_by(Group.created_at.desc(), Group.id.desc())
        ).all()
    )


def get_group_details(session: Session, group_id: int) -> GroupDetails:
    group = session.get(Group, group_id)
    if group is None:
        raise GroupNotFoundError

    members = list(
        session.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.group_id == group_id)
            .order_by(Membership.joined_at, Membership.id)
        ).all()
    )
    return GroupDetails(group=group, members=members)


def delete_group(session: Session, group_id: int, owner_id: int) -> None:
    """Delete a group and all data scoped to it without deleting any users."""
    group = _get_owned_group(session, group_id, owner_id)
    expense_ids = select(Expense.id).where(Expense.group_id == group_id)

    try:
        # Group foreign keys intentionally restrict deletion. Remove only dependent
        # group rows in this transaction, leaving users and other groups untouched.
        session.execute(
            delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids))
        )
        session.execute(delete(Expense).where(Expense.group_id == group_id))
        session.execute(delete(Settlement).where(Settlement.group_id == group_id))
        session.execute(delete(Activity).where(Activity.group_id == group_id))
        session.execute(delete(Membership).where(Membership.group_id == group_id))
        session.delete(group)
        session.commit()
    except Exception:
        session.rollback()
        raise


def add_group_member(session: Session, group_id: int, owner_id: int, email: str) -> Membership:
    """Add an existing user to a group owned by the current user."""
    _get_owned_group(session, group_id, owner_id)
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise MemberUserNotFoundError

    existing_membership = session.scalar(
        select(Membership.id).where(
            Membership.group_id == group_id,
            Membership.user_id == user.id,
        )
    )
    if existing_membership is not None:
        raise MemberAlreadyExistsError

    membership = Membership(group_id=group_id, user_id=user.id)
    session.add(membership)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise MemberAlreadyExistsError from error

    session.refresh(membership)
    return membership


def remove_group_member(
    session: Session,
    group_id: int,
    owner_id: int,
    user_id: int,
) -> None:
    """Remove a zero-balance non-owner member while preserving their account and history."""
    group = _get_owned_group(session, group_id, owner_id)
    if user_id == group.owner_id:
        raise CannotRemoveGroupOwnerError

    membership = session.scalar(
        select(Membership).where(
            Membership.group_id == group_id,
            Membership.user_id == user_id,
        )
    )
    if membership is None:
        raise GroupMemberNotFoundError

    if get_group_member_net_balance(session, group_id, user_id) != 0:
        raise MemberHasNonzeroBalanceError

    try:
        session.delete(membership)
        session.commit()
    except Exception:
        session.rollback()
        raise


def get_group_member_net_balance(session: Session, group_id: int, user_id: int) -> int:
    """Return a member's net position from persisted group financial records.

    Positive values mean the group owes the member; negative values mean the member
    owes the group. The calculation uses persisted expense payments, assigned splits,
    and settlement transfers rather than inventing a temporary balance model.
    """
    paid = session.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.group_id == group_id,
            Expense.paid_by == user_id,
        )
    )
    owed = session.scalar(
        select(func.coalesce(func.sum(ExpenseSplit.amount), 0))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(
            Expense.group_id == group_id,
            ExpenseSplit.user_id == user_id,
        )
    )
    sent = session.scalar(
        select(func.coalesce(func.sum(Settlement.amount), 0)).where(
            Settlement.group_id == group_id,
            Settlement.from_user_id == user_id,
        )
    )
    received = session.scalar(
        select(func.coalesce(func.sum(Settlement.amount), 0)).where(
            Settlement.group_id == group_id,
            Settlement.to_user_id == user_id,
        )
    )
    return int(paid or 0) - int(owed or 0) + int(sent or 0) - int(received or 0)


def _get_owned_group(session: Session, group_id: int, owner_id: int) -> Group:
    group = session.get(Group, group_id)
    if group is None:
        raise GroupNotFoundError
    if group.owner_id != owner_id:
        raise GroupOwnerRequiredError
    return group
