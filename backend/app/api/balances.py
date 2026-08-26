from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_group_member
from app.db.session import get_db_session
from app.models import User
from app.schemas.balances import (
    DebtSuggestionResponse,
    GroupBalancesResponse,
    MemberBalanceResponse,
)
from app.schemas.money import paise_to_rupees
from app.services.balances import calculate_group_balances


router = APIRouter(tags=["balances"])


@router.get(
    "/groups/{group_id}/balances",
    response_model=GroupBalancesResponse,
)
def get_group_balances(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
) -> GroupBalancesResponse:
    del current_user
    result = calculate_group_balances(session, group_id)
    user_names = dict(
        session.execute(
            select(User.id, User.name).where(
                User.id.in_([balance.user_id for balance in result.member_balances])
            )
        ).all()
    )

    return GroupBalancesResponse(
        balances=[
            MemberBalanceResponse(
                user_id=balance.user_id,
                name=user_names[balance.user_id],
                net_balance=paise_to_rupees(balance.net_balance),
            )
            for balance in result.member_balances
        ],
        debts=[
            DebtSuggestionResponse(
                from_user_id=debt.from_user_id,
                from_user_name=user_names[debt.from_user_id],
                to_user_id=debt.to_user_id,
                to_user_name=user_names[debt.to_user_id],
                amount=paise_to_rupees(debt.amount),
            )
            for debt in result.suggested_payments
        ],
    )
