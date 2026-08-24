from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SplitType(StrEnum):
    EQUAL = "equal"
    CUSTOM = "custom"


class CustomSplitRequest(BaseModel):
    user_id: int = Field(gt=0, strict=True)
    amount: int = Field(ge=0, strict=True)


class ExpenseUpsertRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: int = Field(gt=0, strict=True)
    paid_by: int = Field(gt=0, strict=True)
    expense_date: date
    split_type: SplitType
    split_user_ids: list[int] = Field(default_factory=list)
    splits: list[CustomSplitRequest] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("split_user_ids")
    @classmethod
    def validate_split_user_ids(cls, value: list[int]) -> list[int]:
        if any(
            not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0
            for user_id in value
        ):
            raise ValueError("Split user IDs must be positive integers")
        if len(value) != len(set(value)):
            raise ValueError("A user may appear only once in an equal split")
        return value

    @model_validator(mode="after")
    def validate_split_shape(self) -> "ExpenseUpsertRequest":
        if self.split_type is SplitType.EQUAL:
            if not self.split_user_ids:
                raise ValueError("Equal splits require at least one split user")
            if self.splits:
                raise ValueError("Equal splits must use split_user_ids, not custom splits")
        else:
            if not self.splits:
                raise ValueError("Custom splits require at least one split amount")
            if self.split_user_ids:
                raise ValueError("Custom splits must use splits, not split_user_ids")
            user_ids = [split.user_id for split in self.splits]
            if len(user_ids) != len(set(user_ids)):
                raise ValueError("A user may appear only once in a custom split")
        return self


class ExpenseSplitResponse(BaseModel):
    user_id: int
    amount: int


class ExpenseResponse(BaseModel):
    id: int
    group_id: int
    created_by: int
    description: str
    amount: int
    paid_by: int
    expense_date: date
    split_type: SplitType
    created_at: datetime
    updated_at: datetime
    splits: list[ExpenseSplitResponse]


class PaginatedExpensesResponse(BaseModel):
    items: list[ExpenseResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


ExpenseSortField = Literal["date", "amount"]
SortDirection = Literal["asc", "desc"]
