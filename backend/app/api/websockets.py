from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.api.dependencies import get_user_from_access_token
from app.db.session import SessionLocal
from app.models import Membership
from app.realtime.manager import connection_manager


router = APIRouter(tags=["websockets"])


@router.websocket("/ws/groups/{group_id}")
async def group_websocket(websocket: WebSocket, group_id: int) -> None:
    """Keep an authenticated, group-authorized socket open for live events."""
    access_token = _get_access_token(websocket)
    with SessionLocal() as session:
        user = get_user_from_access_token(session, access_token)
        is_member = user is not None and session.scalar(
            select(Membership.id).where(
                Membership.group_id == group_id,
                Membership.user_id == user.id,
            )
        ) is not None
    if not is_member or user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await connection_manager.connect(group_id, user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(group_id, websocket)


def _get_access_token(websocket: WebSocket) -> str | None:
    """Accept a query token or standard Bearer header without new token semantics."""
    query_token = websocket.query_params.get("token")
    if query_token:
        return query_token
    authorization = websocket.headers.get("authorization")
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None
