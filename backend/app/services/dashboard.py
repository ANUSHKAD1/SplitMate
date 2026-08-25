"""Read-only, authenticated dashboard composition."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, Group, Membership
from app.services.balances import calculate_group_balances, calculate_user_overall_balance


@dataclass(frozen=True)
class DashboardDebtGroup:
    group_id: int
    group_name: str
    amount_owed: int


@dataclass(frozen=True)
class DashboardRecentActivity:
    activity: Activity
    group_name: str


@dataclass(frozen=True)
class DashboardResult:
    total_owed_to_user: int
    total_user_owes: int
    net_balance: int
    group_count: int
    group_where_user_owes_most: DashboardDebtGroup | None
    recent_activity: list[DashboardRecentActivity]
    recent_activity_page: int
    recent_activity_page_size: int
    recent_activity_total: int


def get_dashboard(
    session: Session,
    user_id: int,
    activity_page: int,
    activity_page_size: int,
) -> DashboardResult:
    """Build a membership-scoped dashboard without writing to the database."""
    groups = list(
        session.scalars(
            select(Group)
            .join(Membership, Membership.group_id == Group.id)
            .where(Membership.user_id == user_id)
            .order_by(Group.id)
        ).all()
    )
    overall_balance = calculate_user_overall_balance(session, user_id)
    largest_debt = _find_largest_debt(session, user_id, groups)
    recent_activity, total_activity = _recent_activity(
        session, user_id, activity_page, activity_page_size
    )
    return DashboardResult(
        total_owed_to_user=overall_balance.total_owed_to_user,
        total_user_owes=overall_balance.total_user_owes,
        net_balance=overall_balance.net_balance,
        group_count=len(groups),
        group_where_user_owes_most=largest_debt,
        recent_activity=recent_activity,
        recent_activity_page=activity_page,
        recent_activity_page_size=activity_page_size,
        recent_activity_total=total_activity,
    )


def _find_largest_debt(
    session: Session,
    user_id: int,
    groups: list[Group],
) -> DashboardDebtGroup | None:
    debts: list[DashboardDebtGroup] = []
    for group in groups:
        net_balance = calculate_group_balances(session, group.id).balance_for(user_id)
        if net_balance < 0:
            debts.append(
                DashboardDebtGroup(
                    group_id=group.id,
                    group_name=group.name,
                    amount_owed=-net_balance,
                )
            )
    return max(debts, key=lambda debt: debt.amount_owed, default=None)


def _recent_activity(
    session: Session,
    user_id: int,
    page: int,
    page_size: int,
) -> tuple[list[DashboardRecentActivity], int]:
    membership_filter = Membership.user_id == user_id
    total = int(
        session.scalar(
            select(func.count(Activity.id))
            .join(Membership, Membership.group_id == Activity.group_id)
            .where(membership_filter)
        )
        or 0
    )
    rows = session.execute(
        select(Activity, Group.name)
        .join(Membership, Membership.group_id == Activity.group_id)
        .join(Group, Group.id == Activity.group_id)
        .where(membership_filter)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [
        DashboardRecentActivity(activity=activity, group_name=group_name)
        for activity, group_name in rows
    ], total
