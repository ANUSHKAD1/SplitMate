from datetime import datetime

from pydantic import BaseModel, Field


class SettlementCreateRequest(BaseModel):
    to_user_id: int = Field(gt=0, strict=True)
    amount: int = Field(gt=0, strict=True)


class SettlementUserResponse(BaseModel):
    id: int
    name: str
    email: str


class SettlementResponse(BaseModel):
    id: int
    group_id: int
    from_user: SettlementUserResponse
    to_user: SettlementUserResponse
    amount: int
    created_at: datetime
