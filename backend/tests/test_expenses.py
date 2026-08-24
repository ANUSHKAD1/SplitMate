from dataclasses import dataclass
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
class ExpenseUser:
    id: int
    email: str
    token: str


@pytest.fixture
def user_factory() -> Callable[[str], ExpenseUser]:
    created_user_ids: list[int] = []

    def create_user(name: str = "Asha Patel") -> ExpenseUser:
        email = f"expense-test-{uuid4().hex}@example.com"
        with SessionLocal() as session:
            user = User(name=name, email=email, password_hash="not-used")
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return ExpenseUser(user.id, user.email, create_access_token(user.id))

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


def auth_headers(user: ExpenseUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: ExpenseUser) -> int:
    response = client.post(
        "/groups", json={"name": "Expense test group"}, headers=auth_headers(owner)
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def add_member(owner: ExpenseUser, group_id: int, member: ExpenseUser) -> None:
    response = client.post(
        f"/groups/{group_id}/members",
        json={"email": member.email},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201


def equal_payload(
    paid_by: int,
    split_user_ids: list[int],
    amount: int = 100,
    description: str = "Lunch",
    expense_date: str = "2026-08-20",
) -> dict[str, object]:
    return {
        "description": description,
        "amount": amount,
        "paid_by": paid_by,
        "expense_date": expense_date,
        "split_type": "equal",
        "split_user_ids": split_user_ids,
    }


def custom_payload(
    paid_by: int,
    splits: list[dict[str, int]],
    amount: int = 100,
    description: str = "Lunch",
    expense_date: str = "2026-08-20",
) -> dict[str, object]:
    return {
        "description": description,
        "amount": amount,
        "paid_by": paid_by,
        "expense_date": expense_date,
        "split_type": "custom",
        "splits": splits,
    }


def create_expense(
    creator: ExpenseUser,
    group_id: int,
    payload: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        f"/groups/{group_id}/expenses",
        json=payload,
        headers=auth_headers(creator),
    )
    assert response.status_code == 201
    return response.json()


def split_amounts(expense: dict[str, object]) -> dict[int, int]:
    return {
        int(split["user_id"]): int(split["amount"])
        for split in expense["splits"]  # type: ignore[index]
    }


def test_create_equal_split(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    member = user_factory("Member")
    group_id = create_group(owner)
    add_member(owner, group_id, member)

    expense = create_expense(
        owner, group_id, equal_payload(owner.id, [owner.id, member.id])
    )

    assert expense["split_type"] == "equal"
    assert split_amounts(expense) == {owner.id: 50, member.id: 50}


def test_uneven_equal_split_assigns_remainder_in_request_order(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    first_member = user_factory("First")
    second_member = user_factory("Second")
    group_id = create_group(owner)
    add_member(owner, group_id, first_member)
    add_member(owner, group_id, second_member)

    expense = create_expense(
        owner,
        group_id,
        equal_payload(
            owner.id,
            [first_member.id, second_member.id, owner.id],
            amount=100,
        ),
    )

    assert split_amounts(expense) == {
        first_member.id: 34,
        second_member.id: 33,
        owner.id: 33,
    }
    assert sum(split_amounts(expense).values()) == 100


def test_create_exact_custom_split(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    member = user_factory("Member")
    group_id = create_group(owner)
    add_member(owner, group_id, member)

    expense = create_expense(
        owner,
        group_id,
        custom_payload(
            owner.id,
            [{"user_id": owner.id, "amount": 25}, {"user_id": member.id, "amount": 75}],
        ),
    )

    assert expense["split_type"] == "custom"
    assert split_amounts(expense) == {owner.id: 25, member.id: 75}


def test_custom_split_total_mismatch_is_rejected(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    group_id = create_group(owner)

    response = client.post(
        f"/groups/{group_id}/expenses",
        json=custom_payload(owner.id, [{"user_id": owner.id, "amount": 99}]),
        headers=auth_headers(owner),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Custom split amounts must equal the expense amount"
    }


@pytest.mark.parametrize("amount", [0, -1])
def test_zero_or_negative_amount_is_rejected(
    user_factory: Callable[[str], ExpenseUser], amount: int
) -> None:
    owner = user_factory()
    group_id = create_group(owner)

    response = client.post(
        f"/groups/{group_id}/expenses",
        json=equal_payload(owner.id, [owner.id], amount=amount),
        headers=auth_headers(owner),
    )

    assert response.status_code == 422


def test_non_member_payer_is_rejected(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    outsider = user_factory("Outsider")
    group_id = create_group(owner)

    response = client.post(
        f"/groups/{group_id}/expenses",
        json=equal_payload(outsider.id, [owner.id]),
        headers=auth_headers(owner),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "The payer must be a member of this group"}


def test_non_member_split_user_is_rejected(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    outsider = user_factory("Outsider")
    group_id = create_group(owner)

    response = client.post(
        f"/groups/{group_id}/expenses",
        json=equal_payload(owner.id, [owner.id, outsider.id]),
        headers=auth_headers(owner),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Every split user must be a member of this group"
    }


def test_non_member_cannot_create_or_list_expenses(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    outsider = user_factory("Outsider")
    group_id = create_group(owner)

    create_response = client.post(
        f"/groups/{group_id}/expenses",
        json=equal_payload(owner.id, [owner.id]),
        headers=auth_headers(outsider),
    )
    list_response = client.get(
        f"/groups/{group_id}/expenses", headers=auth_headers(outsider)
    )

    assert create_response.status_code == 403
    assert list_response.status_code == 403


def test_non_creator_non_owner_cannot_edit_expense(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    creator = user_factory("Creator")
    other_member = user_factory("Other")
    group_id = create_group(owner)
    add_member(owner, group_id, creator)
    add_member(owner, group_id, other_member)
    expense = create_expense(creator, group_id, equal_payload(creator.id, [creator.id]))

    response = client.put(
        f"/expenses/{expense['id']}",
        json=equal_payload(creator.id, [creator.id], description="Changed"),
        headers=auth_headers(other_member),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Only the expense creator or group owner can edit this expense"
    }


def test_non_creator_non_owner_cannot_delete_expense(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    creator = user_factory("Creator")
    other_member = user_factory("Other")
    group_id = create_group(owner)
    add_member(owner, group_id, creator)
    add_member(owner, group_id, other_member)
    expense = create_expense(creator, group_id, equal_payload(creator.id, [creator.id]))

    response = client.delete(
        f"/expenses/{expense['id']}", headers=auth_headers(other_member)
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Only the expense creator or group owner can delete this expense"
    }


def test_edit_replaces_split_rows_safely(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    first_member = user_factory("First")
    second_member = user_factory("Second")
    group_id = create_group(owner)
    add_member(owner, group_id, first_member)
    add_member(owner, group_id, second_member)
    expense = create_expense(
        owner, group_id, equal_payload(owner.id, [owner.id, first_member.id])
    )

    response = client.put(
        f"/expenses/{expense['id']}",
        json=custom_payload(
            owner.id,
            [{"user_id": owner.id, "amount": 20}, {"user_id": second_member.id, "amount": 80}],
            description="Updated lunch",
        ),
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Updated lunch"
    assert split_amounts(response.json()) == {owner.id: 20, second_member.id: 80}
    with SessionLocal() as session:
        split_user_ids = set(
            session.scalars(
                select(ExpenseSplit.user_id).where(ExpenseSplit.expense_id == expense["id"])
            )
        )
    assert split_user_ids == {owner.id, second_member.id}


def test_delete_removes_expense_and_split_rows(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    group_id = create_group(owner)
    expense = create_expense(owner, group_id, equal_payload(owner.id, [owner.id]))

    response = client.delete(f"/expenses/{expense['id']}", headers=auth_headers(owner))

    assert response.status_code == 204
    with SessionLocal() as session:
        deleted_expense = session.get(Expense, expense["id"])
        split_rows = list(
            session.scalars(
                select(ExpenseSplit).where(ExpenseSplit.expense_id == expense["id"])
            )
        )
    assert deleted_expense is None
    assert split_rows == []


def test_expense_pagination_uses_requested_page_and_size(
    user_factory: Callable[[str], ExpenseUser],
) -> None:
    owner = user_factory()
    group_id = create_group(owner)
    first = create_expense(owner, group_id, equal_payload(owner.id, [owner.id]))
    second = create_expense(owner, group_id, equal_payload(owner.id, [owner.id]))
    third = create_expense(owner, group_id, equal_payload(owner.id, [owner.id]))

    response = client.get(
        f"/groups/{group_id}/expenses?page=2&page_size=1",
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert response.json()["total_pages"] == 3
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 1
    assert [item["id"] for item in response.json()["items"]] == [second["id"]]
    assert first["id"] != third["id"]


def test_expense_sorting_by_date(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    group_id = create_group(owner)
    newest = create_expense(
        owner, group_id, equal_payload(owner.id, [owner.id], expense_date="2026-08-22")
    )
    oldest = create_expense(
        owner, group_id, equal_payload(owner.id, [owner.id], expense_date="2026-08-20")
    )

    response = client.get(
        f"/groups/{group_id}/expenses?sort_by=date&sort_order=asc",
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        oldest["id"],
        newest["id"],
    ]


def test_expense_sorting_by_amount(user_factory: Callable[[str], ExpenseUser]) -> None:
    owner = user_factory()
    group_id = create_group(owner)
    high = create_expense(owner, group_id, equal_payload(owner.id, [owner.id], amount=300))
    low = create_expense(owner, group_id, equal_payload(owner.id, [owner.id], amount=100))

    response = client.get(
        f"/groups/{group_id}/expenses?sort_by=amount&sort_order=asc",
        headers=auth_headers(owner),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [low["id"], high["id"]]
