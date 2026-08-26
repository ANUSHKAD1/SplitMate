from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_group_member
from app.db.session import get_db_session
from app.models import Settlement, User
from app.schemas.settlements import (
    SettlementCreateRequest,
    SettlementResponse,
    SettlementUserResponse,
)
from app.schemas.money import paise_to_rupees
from app.services.settlements import (
    SettlementValidationError,
    create_settlement,
    list_group_settlements,
)


router = APIRouter(tags=["settlements"])


@router.post(
    "/groups/{group_id}/settlements",
    response_model=SettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_settlement_endpoint(
    group_id: int,
    request: SettlementCreateRequest,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
) -> SettlementResponse:
    settlement_data = request.to_paise()
    try:
        settlement = create_settlement(
            session,
            group_id,
            current_user.id,
            settlement_data.to_user_id,
            settlement_data.amount,
        )
    except SettlementValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return _settlement_response(settlement)


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementResponse])
def list_settlements_endpoint(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
) -> list[SettlementResponse]:
    del current_user
    return [
        _settlement_response(settlement)
        for settlement in list_group_settlements(session, group_id)
    ]


def _settlement_response(settlement: Settlement) -> SettlementResponse:
    return SettlementResponse(
        id=settlement.id,
        group_id=settlement.group_id,
        from_user=SettlementUserResponse(
            id=settlement.from_user.id,
            name=settlement.from_user.name,
            email=settlement.from_user.email,
        ),
        to_user=SettlementUserResponse(
            id=settlement.to_user.id,
            name=settlement.to_user.name,
            email=settlement.to_user.email,
        ),
        amount=paise_to_rupees(settlement.amount),
        created_at=settlement.created_at,
    )
