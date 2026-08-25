from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_group_member
from app.db.session import get_db_session
from app.models import Activity, User
from app.schemas.activities import ActivityResponse, PaginatedActivitiesResponse
from app.services.activities import list_group_activities


router = APIRouter(tags=["activities"])


@router.get(
    "/groups/{group_id}/activity",
    response_model=PaginatedActivitiesResponse,
)
def list_activities_endpoint(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedActivitiesResponse:
    del current_user
    activity_page = list_group_activities(session, group_id, page, page_size)
    return PaginatedActivitiesResponse(
        items=[_activity_response(activity) for activity in activity_page.activities],
        page=activity_page.page,
        page_size=activity_page.page_size,
        total=activity_page.total,
        total_pages=(activity_page.total + activity_page.page_size - 1)
        // activity_page.page_size,
    )


def _activity_response(activity: Activity) -> ActivityResponse:
    return ActivityResponse(
        id=activity.id,
        group_id=activity.group_id,
        user_id=activity.user_id,
        event_type=activity.event_type,
        message=activity.message,
        created_at=activity.created_at,
    )
