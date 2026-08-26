from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models import User
from app.schemas.dashboard import (
    DashboardDebtGroupResponse,
    DashboardRecentActivityResponse,
    DashboardResponse,
)
from app.schemas.money import paise_to_rupees
from app.services.dashboard import DashboardResult, get_dashboard


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> DashboardResponse:
    result = get_dashboard(session, current_user.id, page, page_size)
    return _dashboard_response(result)


def _dashboard_response(result: DashboardResult) -> DashboardResponse:
    debt_group = result.group_where_user_owes_most
    return DashboardResponse(
        total_owed_to_user=paise_to_rupees(result.total_owed_to_user),
        total_user_owes=paise_to_rupees(result.total_user_owes),
        net_balance=paise_to_rupees(result.net_balance),
        group_count=result.group_count,
        group_where_user_owes_most=(
            DashboardDebtGroupResponse(
                group_id=debt_group.group_id,
                group_name=debt_group.group_name,
                amount_owed=paise_to_rupees(debt_group.amount_owed),
            )
            if debt_group is not None
            else None
        ),
        recent_activity=[
            DashboardRecentActivityResponse(
                id=item.activity.id,
                group_id=item.activity.group_id,
                group_name=item.group_name,
                user_id=item.activity.user_id,
                event_type=item.activity.event_type,
                message=item.activity.message,
                created_at=item.activity.created_at,
            )
            for item in result.recent_activity
        ],
        recent_activity_page=result.recent_activity_page,
        recent_activity_page_size=result.recent_activity_page_size,
        recent_activity_total=result.recent_activity_total,
        recent_activity_total_pages=(
            result.recent_activity_total + result.recent_activity_page_size - 1
        )
        // result.recent_activity_page_size,
    )
