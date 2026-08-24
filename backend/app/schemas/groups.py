from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class GroupResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupMemberResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    joined_at: datetime


class GroupDetailResponse(GroupResponse):
    members: list[GroupMemberResponse]


class AddGroupMemberRequest(BaseModel):
    email: EmailStr = Field(max_length=320)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value
