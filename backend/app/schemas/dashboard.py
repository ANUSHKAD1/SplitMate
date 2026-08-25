from datetime import datetime

from pydantic import BaseModel


class DashboardDebtGroupResponse(BaseModel):
    group_id: int
    group_name: str
    amount_owed: int


class DashboardRecentActivityResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    user_id: int
    event_type: str
    message: str
    created_at: datetime


class DashboardResponse(BaseModel):
    total_owed_to_user: int
    total_user_owes: int
    net_balance: int
    group_count: int
    group_where_user_owes_most: DashboardDebtGroupResponse | None
    recent_activity: list[DashboardRecentActivityResponse]
    recent_activity_page: int
    recent_activity_page_size: int
    recent_activity_total: int
    recent_activity_total_pages: int
