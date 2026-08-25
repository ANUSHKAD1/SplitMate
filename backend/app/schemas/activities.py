from datetime import datetime

from pydantic import BaseModel


class ActivityResponse(BaseModel):
    id: int
    group_id: int
    user_id: int
    event_type: str
    message: str
    created_at: datetime


class PaginatedActivitiesResponse(BaseModel):
    items: list[ActivityResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
