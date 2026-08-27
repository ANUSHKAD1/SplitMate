"""Create repeatable development demo data for SplitMate.

Run from the backend directory after applying migrations:

    python -m scripts.seed_demo
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Expense, Group, Membership, Settlement, User
from app.schemas.auth import RegistrationRequest
from app.schemas.expenses import CustomSplitData, ExpenseUpsertData, SplitType
from app.services.auth import register_user
from app.services.balances import calculate_group_balances
from app.services.expenses import create_expense
from app.services.groups import add_group_member, create_group
from app.services.settlements import create_settlement


DEMO_PASSWORD = "SplitMateDemo123!"
GROUP_NAME = "Rosy Birthday Party"
SETTLEMENT_AMOUNT = 50_000  # ₹500.00, represented in integer paise.


@dataclass(frozen=True)
class DemoExpense:
    description: str
    amount: int
    paid_by: str
    expense_date: date
    split_type: SplitType
    split_amounts: dict[str, int] | None = None


DEMO_EXPENSES = (
    DemoExpense(
        description="Birthday venue deposit",
        amount=300_000,  # ₹3,000.00
        paid_by="rosy",
        expense_date=date(2026, 8, 20),
        split_type=SplitType.EQUAL,
    ),
    DemoExpense(
        description="Birthday decorations",
        amount=120_000,  # ₹1,200.00
        paid_by="anu",
        expense_date=date(2026, 8, 22),
        split_type=SplitType.CUSTOM,
        split_amounts={"rosy": 75_000, "anu": 45_000},
    ),
    DemoExpense(
        description="Birthday cake",
        amount=90_000,  # ₹900.00
        paid_by="rosy",
        expense_date=date(2026, 8, 24),
        split_type=SplitType.EQUAL,
    ),
)


def get_or_create_user(session: Session, name: str, email: str) -> tuple[User, bool]:
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        return user, False

    user = register_user(
        session,
        RegistrationRequest(name=name, email=email, password=DEMO_PASSWORD),
    )
    return user, True


def get_or_create_group(session: Session, owner: User) -> tuple[Group, bool]:
    group = session.scalar(
        select(Group)
        .where(Group.name == GROUP_NAME, Group.owner_id == owner.id)
        .order_by(Group.id)
    )
    if group is not None:
        return group, False
    return create_group(session, owner.id, GROUP_NAME), True


def ensure_membership(session: Session, group: Group, user: User, owner: User) -> bool:
    membership = session.scalar(
        select(Membership.id).where(
            Membership.group_id == group.id,
            Membership.user_id == user.id,
        )
    )
    if membership is not None:
        return False

    if user.id == owner.id:
        # This only repairs a manually altered existing group. New groups are
        # created through create_group(), which adds the owner membership.
        session.add(Membership(group_id=group.id, user_id=user.id))
        session.commit()
    else:
        add_group_member(session, group.id, owner.id, user.email)
    return True


def ensure_expenses(session: Session, group: Group, users: dict[str, User]) -> int:
    existing_descriptions = set(
        session.scalars(
            select(Expense.description).where(Expense.group_id == group.id)
        ).all()
    )
    created_count = 0

    for demo_expense in DEMO_EXPENSES:
        if demo_expense.description in existing_descriptions:
            continue

        participant_ids = [users["rosy"].id, users["anu"].id]
        custom_splits = [
            CustomSplitData(user_id=users[name].id, amount=amount)
            for name, amount in (demo_expense.split_amounts or {}).items()
        ]
        create_expense(
            session,
            group.id,
            users[demo_expense.paid_by].id,
            ExpenseUpsertData(
                description=demo_expense.description,
                amount=demo_expense.amount,
                paid_by=users[demo_expense.paid_by].id,
                expense_date=demo_expense.expense_date,
                split_type=demo_expense.split_type,
                split_user_ids=(
                    participant_ids if demo_expense.split_type is SplitType.EQUAL else []
                ),
                splits=custom_splits,
            ),
        )
        existing_descriptions.add(demo_expense.description)
        created_count += 1

    return created_count


def ensure_settlement(session: Session, group: Group, rosy: User, anu: User) -> bool:
    existing_settlement = session.scalar(
        select(Settlement.id).where(
            Settlement.group_id == group.id,
            Settlement.from_user_id == anu.id,
            Settlement.to_user_id == rosy.id,
            Settlement.amount == SETTLEMENT_AMOUNT,
        )
    )
    if existing_settlement is not None:
        return False

    balances = calculate_group_balances(session, group.id)
    if (
        balances.balance_for(anu.id) >= 0
        or balances.balance_for(rosy.id) <= 0
        or min(-balances.balance_for(anu.id), balances.balance_for(rosy.id))
        < SETTLEMENT_AMOUNT
    ):
        return False

    create_settlement(session, group.id, anu.id, rosy.id, SETTLEMENT_AMOUNT)
    return True


def seed_demo_data() -> None:
    with SessionLocal() as session:
        rosy, rosy_created = get_or_create_user(session, "Rosy", "rosy@splitmate.demo")
        anu, anu_created = get_or_create_user(session, "Anu", "anu@splitmate.demo")
        group, group_created = get_or_create_group(session, rosy)
        rosy_membership_created = ensure_membership(session, group, rosy, rosy)
        anu_membership_created = ensure_membership(session, group, anu, rosy)
        expenses_created = ensure_expenses(session, group, {"rosy": rosy, "anu": anu})
        settlement_created = ensure_settlement(session, group, rosy, anu)
        balances = calculate_group_balances(session, group.id)

    print(f"Demo group: {GROUP_NAME} (id={group.id})")
    print(f"Users created: Rosy={rosy_created}, Anu={anu_created}")
    print(
        "Memberships created: "
        f"Rosy={rosy_membership_created}, Anu={anu_membership_created}"
    )
    print(f"Group created: {group_created}; expenses created: {expenses_created}")
    print(f"Settlement created: {settlement_created}")
    print(
        "Current balances (paise): "
        f"Rosy={balances.balance_for(rosy.id)}, Anu={balances.balance_for(anu.id)}"
    )


if __name__ == "__main__":
    seed_demo_data()
