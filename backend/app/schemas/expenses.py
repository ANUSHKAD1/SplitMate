from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.money import parse_rupee_amount, rupees_to_paise


class SplitType(StrEnum):
    EQUAL = "equal"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CustomSplitData:
    """Internal expense split input, expressed in integer paise."""

    user_id: int
    amount: int


@dataclass(frozen=True)
class ExpenseUpsertData:
    """Internal expense input passed to the domain service in integer paise."""

    description: str
    amount: int
    paid_by: int
    expense_date: date
    split_type: SplitType
    split_user_ids: list[int]
    splits: list[CustomSplitData]


class CustomSplitRequest(BaseModel):
    user_id: int = Field(gt=0, strict=True)
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        amount = parse_rupee_amount(value)
        if amount < 0:
            raise ValueError("Split amounts cannot be negative")
        return amount


class ExpenseUpsertRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal
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

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        amount = parse_rupee_amount(value)
        if amount <= 0:
            raise ValueError("Expense amount must be positive")
        return amount

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

    def to_paise(self) -> ExpenseUpsertData:
        """Convert public rupee inputs to the service's integer-paise contract."""
        return ExpenseUpsertData(
            description=self.description,
            amount=rupees_to_paise(self.amount),
            paid_by=self.paid_by,
            expense_date=self.expense_date,
            split_type=self.split_type,
            split_user_ids=self.split_user_ids,
            splits=[
                CustomSplitData(
                    user_id=split.user_id,
                    amount=rupees_to_paise(split.amount),
                )
                for split in self.splits
            ],
        )


class ExpenseSplitResponse(BaseModel):
    user_id: int
    amount: str


class ExpenseResponse(BaseModel):
    id: int
    group_id: int
    created_by: int
    description: str
    amount: str
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
