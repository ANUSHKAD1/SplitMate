import asyncio
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models import Activity, Expense, ExpenseSplit, Group, Membership, Settlement, User
from app.realtime.manager import ConnectionManager, connection_manager


client = TestClient(app)


@dataclass(frozen=True)
class SocketUser:
    id: int
    email: str
    token: str


class FakeWebSocket:
    def __init__(self, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.accepted = False
        self.messages: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict[str, object]) -> None:
        if self.fail_send:
            raise RuntimeError("socket closed")
        self.messages.append(message)

    async def close(self, code: int = 1000) -> None:
        del code


@pytest.fixture(autouse=True)
def reset_connection_manager() -> None:
    connection_manager._connections.clear()
    yield
    connection_manager._connections.clear()


@pytest.fixture
def user_factory() -> Callable[[str], SocketUser]:
    created_user_ids: list[int] = []

    def create_user(name: str = "Socket User") -> SocketUser:
        with SessionLocal() as session:
            user = User(
                name=name,
                email=f"socket-{uuid4().hex}@example.com",
                password_hash="not-used",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            created_user_ids.append(user.id)
            return SocketUser(user.id, user.email, create_access_token(user.id))

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
            session.execute(delete(Activity).where(Activity.group_id.in_(group_ids)))
            session.execute(delete(Membership).where(Membership.group_id.in_(group_ids)))
            session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if created_user_ids:
            session.execute(delete(Membership).where(Membership.user_id.in_(created_user_ids)))
            session.execute(delete(User).where(User.id.in_(created_user_ids)))
        session.commit()


def auth_headers(user: SocketUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


def create_group(owner: SocketUser) -> int:
    response = client.post(
        "/groups", json={"name": "Socket group"}, headers=auth_headers(owner)
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def add_member(owner: SocketUser, group_id: int, member: SocketUser) -> None:
    response = client.post(
        f"/groups/{group_id}/members",
        json={"email": member.email},
        headers=auth_headers(owner),
    )
    assert response.status_code == 201


def create_expense(owner: SocketUser, group_id: int, split_user_id: int) -> dict[str, object]:
    response = client.post(
        f"/groups/{group_id}/expenses",
        json={
            "description": "Lunch",
            "amount": 100,
            "paid_by": owner.id,
            "expense_date": "2026-08-20",
            "split_type": "equal",
            "split_user_ids": [split_user_id],
        },
        headers=auth_headers(owner),
    )
    assert response.status_code == 201
    return response.json()


def receive_event(socket, event_type: str) -> dict[str, object]:
    for _ in range(4):
        event = socket.receive_json()
        if event["type"] == event_type:
            return event
    raise AssertionError(f"Did not receive {event_type}")


def test_authenticated_group_member_can_connect(
    user_factory: Callable[[str], SocketUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)

    with client.websocket_connect(f"/ws/groups/{group_id}?token={owner.token}"):
        assert connection_manager.connection_count(group_id) == 1

    assert connection_manager.connection_count(group_id) == 0


def test_unauthenticated_socket_connection_is_rejected(
    user_factory: Callable[[str], SocketUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/ws/groups/{group_id}"):
            pass

    assert error.value.code == 1008


def test_non_member_socket_connection_is_rejected(
    user_factory: Callable[[str], SocketUser],
) -> None:
    owner = user_factory("Owner")
    outsider = user_factory("Outsider")
    group_id = create_group(owner)

    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(f"/ws/groups/{group_id}?token={outsider.token}"):
            pass

    assert error.value.code == 1008


def test_group_events_are_never_broadcast_globally() -> None:
    manager = ConnectionManager()
    group_a_socket = FakeWebSocket()
    group_b_socket = FakeWebSocket()

    async def run() -> None:
        await manager.connect(1, 10, group_a_socket)  # type: ignore[arg-type]
        await manager.connect(2, 20, group_b_socket)  # type: ignore[arg-type]
        await manager.broadcast(1, "expense_added", {"expense_id": 5})

    asyncio.run(run())

    assert group_a_socket.messages == [
        {"type": "expense_added", "group_id": 1, "payload": {"expense_id": 5}}
    ]
    assert group_b_socket.messages == []


def test_expense_add_edit_and_delete_reach_group_members(
    user_factory: Callable[[str], SocketUser],
) -> None:
    owner = user_factory("Owner")
    member = user_factory("Member")
    group_id = create_group(owner)
    add_member(owner, group_id, member)

    with client.websocket_connect(f"/ws/groups/{group_id}?token={owner.token}") as owner_socket:
        with client.websocket_connect(
            f"/ws/groups/{group_id}?token={member.token}"
        ) as member_socket:
            expense = create_expense(owner, group_id, member.id)
            for socket in (owner_socket, member_socket):
                event = receive_event(socket, "expense_added")
                assert event["group_id"] == group_id
                assert event["payload"] == {"expense_id": expense["id"]}

            update = client.put(
                f"/expenses/{expense['id']}",
                json={
                    "description": "Updated lunch",
                    "amount": 100,
                    "paid_by": owner.id,
                    "expense_date": "2026-08-20",
                    "split_type": "equal",
                    "split_user_ids": [member.id],
                },
                headers=auth_headers(owner),
            )
            assert update.status_code == 200
            for socket in (owner_socket, member_socket):
                assert receive_event(socket, "expense_edited")["group_id"] == group_id

            deleted = client.delete(f"/expenses/{expense['id']}", headers=auth_headers(owner))
            assert deleted.status_code == 204
            for socket in (owner_socket, member_socket):
                assert receive_event(socket, "expense_deleted")["group_id"] == group_id


def test_settlement_and_activity_events_reach_group_members(
    user_factory: Callable[[str], SocketUser],
) -> None:
    creditor = user_factory("Creditor")
    debtor = user_factory("Debtor")
    group_id = create_group(creditor)
    add_member(creditor, group_id, debtor)
    create_expense(creditor, group_id, debtor.id)

    with client.websocket_connect(f"/ws/groups/{group_id}?token={creditor.token}") as socket:
        settlement = client.post(
            f"/groups/{group_id}/settlements",
            json={"to_user_id": creditor.id, "amount": 100},
            headers=auth_headers(debtor),
        )
        assert settlement.status_code == 201
        assert receive_event(socket, "settlement_recorded")["group_id"] == group_id
        activity_event = receive_event(socket, "activity_added")
        assert activity_event["payload"]["event_type"] == "settlement_recorded"
        assert receive_event(socket, "balances_updated")["group_id"] == group_id


def test_failed_socket_send_is_removed_without_breaking_rest_operation(
    user_factory: Callable[[str], SocketUser], monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)
    failing_socket = FakeWebSocket(fail_send=True)
    manager = ConnectionManager()

    async def fail_delivery() -> None:
        await manager.connect(group_id, owner.id, failing_socket)  # type: ignore[arg-type]
        await manager.broadcast(group_id, "expense_added", {"expense_id": 1})

    asyncio.run(fail_delivery())
    assert manager.connection_count(group_id) == 0

    def failed_delivery(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("socket send failed")

    monkeypatch.setattr(connection_manager, "broadcast_from_sync", failed_delivery)
    response = client.post(
        f"/groups/{group_id}/expenses",
        json={
            "description": "No client needed",
            "amount": 100,
            "paid_by": owner.id,
            "expense_date": "2026-08-20",
            "split_type": "equal",
            "split_user_ids": [owner.id],
        },
        headers=auth_headers(owner),
    )

    assert response.status_code == 201
    assert connection_manager.connection_count(group_id) == 0


def test_rest_behavior_remains_valid_with_no_websocket_clients(
    user_factory: Callable[[str], SocketUser],
) -> None:
    owner = user_factory("Owner")
    group_id = create_group(owner)

    expense = create_expense(owner, group_id, owner.id)

    assert expense["group_id"] == group_id
    assert connection_manager.connection_count(group_id) == 0
