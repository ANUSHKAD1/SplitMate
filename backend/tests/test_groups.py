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
from app.models import Activity, Expense, ExpenseSplit, Group, Membership, Settlement, User


client = TestClient(app)


@dataclass(frozen=True)
class GroupUser:
    id: int
    email: str
    token: str


@pytest.fixture
def user_factory() -> Callable[[str], GroupUser]:
    created_user_ids: list[int] = []

    def create_user(name: str = "Asha Patel") -> GroupUser:
        email = f"group-test-{uuid4().hex}@example.com"
        with SessionLocal() as session:
            user = User(name=name, email=email, password_hash="not-used")
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return GroupUser(
                id=user.id,
                email=user.email,
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
            session.execute(
                delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids))
            )
            session.execute(delete(Expense).where(Expense.group_id.in_(group_ids)))
            session.execute(delete(Settlement).where(Settlement.group_id.in_(group_ids)))
            session.execute(delete(Activity).where(Activity.group_id.in_(group_ids)))
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))

        if created_user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(created_user_ids)))
            session.execute(delete(User).where(User.id.in_(created_user_ids)))
        session.commit()


def auth_headers(user: GroupUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: GroupUser, name: str = "Weekend trip") -> dict[str, object]:
    response = client.post("/groups", json={"name": name}, headers=auth_headers(owner))

    assert response.status_code == 201
    return response.json()


def add_member(owner: GroupUser, group_id: int, member: GroupUser):
    return client.post(
        f"/groups/{group_id}/members",
        json={"email": member.email},
        headers=auth_headers(owner),
    )


def test_authenticated_user_creates_group_as_owner_and_member(
    user_factory: Callable[[str], GroupUser],
) -> None:
    creator = user_factory()

    created_group = create_group(creator, "  Goa trip  ")
    detail_response = client.get(
        f"/groups/{created_group['id']}",
        headers=auth_headers(creator),
    )

    assert created_group["name"] == "Goa trip"
    assert created_group["owner_id"] == creator.id
    assert detail_response.status_code == 200
    assert detail_response.json()["members"] == [
        {
            "id": creator.id,
            "name": "Asha Patel",
            "email": creator.email,
            "joined_at": detail_response.json()["members"][0]["joined_at"],
        }
    ]

    with SessionLocal() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.group_id == created_group["id"],
                Membership.user_id == creator.id,
            )
        )
    assert membership is not None


def test_user_sees_only_groups_they_belong_to(
    user_factory: Callable[[str], GroupUser],
) -> None:
    member = user_factory()
    unrelated_user = user_factory("Unrelated User")
    member_group = create_group(member, "Member group")
    unrelated_group = create_group(unrelated_user, "Unrelated group")

    response = client.get("/groups", headers=auth_headers(member))

    assert response.status_code == 200
    assert [group["id"] for group in response.json()] == [member_group["id"]]
    assert unrelated_group["id"] not in [group["id"] for group in response.json()]


def test_non_member_cannot_view_group_detail(
    user_factory: Callable[[str], GroupUser],
) -> None:
    owner = user_factory()
    outsider = user_factory("Outsider")
    group = create_group(owner)

    response = client.get(f"/groups/{group['id']}", headers=auth_headers(outsider))

    assert response.status_code == 403
    assert response.json() == {"detail": "You are not a member of this group"}


def test_non_owner_cannot_delete_group(user_factory: Callable[[str], GroupUser]) -> None:
    owner = user_factory()
    non_owner = user_factory("Non Owner")
    group = create_group(owner)
    assert add_member(owner, int(group["id"]), non_owner).status_code == 201

    response = client.delete(
        f"/groups/{group['id']}",
        headers=auth_headers(non_owner),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Only the group owner can delete this group"}


def test_owner_can_add_another_registered_user(
    user_factory: Callable[[str], GroupUser],
) -> None:
    owner = user_factory()
    member = user_factory("New Member")
    group = create_group(owner)

    response = add_member(owner, int(group["id"]), member)

    assert response.status_code == 201
    assert response.json()["id"] == member.id
    assert response.json()["email"] == member.email
    with SessionLocal() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.group_id == group["id"],
                Membership.user_id == member.id,
            )
        )
    assert membership is not None


def test_duplicate_membership_is_rejected(user_factory: Callable[[str], GroupUser]) -> None:
    owner = user_factory()
    member = user_factory("New Member")
    group = create_group(owner)
    assert add_member(owner, int(group["id"]), member).status_code == 201

    response = add_member(owner, int(group["id"]), member)

    assert response.status_code == 409
    assert response.json() == {"detail": "User is already a member of this group"}


def test_unknown_member_email_is_rejected(user_factory: Callable[[str], GroupUser]) -> None:
    owner = user_factory()
    group = create_group(owner)

    response = client.post(
        f"/groups/{group['id']}/members",
        json={"email": "missing-user@example.com"},
        headers=auth_headers(owner),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No registered user exists with this email"}


def test_owner_cannot_remove_themselves(user_factory: Callable[[str], GroupUser]) -> None:
    owner = user_factory()
    group = create_group(owner)

    response = client.delete(
        f"/groups/{group['id']}/members/{owner.id}",
        headers=auth_headers(owner),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "The group owner cannot be removed"}


def test_member_with_nonzero_balance_cannot_be_removed(
    user_factory: Callable[[str], GroupUser],
) -> None:
    owner = user_factory()
    member = user_factory("Member With Balance")
    group = create_group(owner)
    group_id = int(group["id"])
    assert add_member(owner, group_id, member).status_code == 201

    with SessionLocal() as session:
        expense = Expense(
            group_id=group_id,
            created_by=owner.id,
            description="Hotel",
            amount=1_000,
            paid_by=owner.id,
            expense_date=date.today(),
        )
        session.add(expense)
        session.flush()
        session.add(ExpenseSplit(expense_id=expense.id, user_id=member.id, amount=1_000))
        session.commit()

    response = client.delete(
        f"/groups/{group_id}/members/{member.id}",
        headers=auth_headers(owner),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Member has a non-zero balance and cannot be removed"
    }


def test_zero_balance_member_can_be_removed_without_deleting_their_account(
    user_factory: Callable[[str], GroupUser],
) -> None:
    owner = user_factory()
    member = user_factory("Zero Balance Member")
    group = create_group(owner)
    group_id = int(group["id"])
    assert add_member(owner, group_id, member).status_code == 201

    with SessionLocal() as session:
        expense = Expense(
            group_id=group_id,
            created_by=owner.id,
            description="Dinner",
            amount=500,
            paid_by=owner.id,
            expense_date=date.today(),
        )
        session.add(expense)
        session.flush()
        split = ExpenseSplit(expense_id=expense.id, user_id=member.id, amount=500)
        session.add(split)
        session.add(
            Settlement(
                group_id=group_id,
                from_user_id=member.id,
                to_user_id=owner.id,
                amount=500,
            )
        )
        session.commit()
        split_id = split.id

    response = client.delete(
        f"/groups/{group_id}/members/{member.id}",
        headers=auth_headers(owner),
    )

    assert response.status_code == 204
    with SessionLocal() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.group_id == group_id,
                Membership.user_id == member.id,
            )
        )
        user = session.get(User, member.id)
        split_after_removal = session.get(ExpenseSplit, split_id)
    assert membership is None
    assert user is not None
    assert split_after_removal is not None


def test_deleting_group_does_not_delete_users(user_factory: Callable[[str], GroupUser]) -> None:
    owner = user_factory()
    member = user_factory("Member")
    group = create_group(owner)
    group_id = int(group["id"])
    assert add_member(owner, group_id, member).status_code == 201

    response = client.delete(f"/groups/{group_id}", headers=auth_headers(owner))

    assert response.status_code == 204
    with SessionLocal() as session:
        deleted_group = session.get(Group, group_id)
        owner_after_deletion = session.get(User, owner.id)
        member_after_deletion = session.get(User, member.id)
        memberships = list(
            session.scalars(select(Membership).where(Membership.group_id == group_id))
        )
    assert deleted_group is None
    assert owner_after_deletion is not None
    assert member_after_deletion is not None
    assert memberships == []
