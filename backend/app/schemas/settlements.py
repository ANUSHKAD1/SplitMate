from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.money import parse_rupee_amount, rupees_to_paise


@dataclass(frozen=True)
class SettlementCreateData:
    """Internal settlement input, expressed in integer paise."""

    to_user_id: int
    amount: int


class SettlementCreateRequest(BaseModel):
    to_user_id: int = Field(gt=0, strict=True)
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> Decimal:
        amount = parse_rupee_amount(value)
        if amount <= 0:
            raise ValueError("Settlement amount must be positive")
        return amount

    def to_paise(self) -> SettlementCreateData:
        """Convert the public rupee input to the service's paise contract."""
        return SettlementCreateData(
            to_user_id=self.to_user_id,
            amount=rupees_to_paise(self.amount),
        )


class SettlementUserResponse(BaseModel):
    id: int
    name: str
    email: str


class SettlementResponse(BaseModel):
    id: int
    group_id: int
    from_user: SettlementUserResponse
    to_user: SettlementUserResponse
    amount: str
    created_at: datetime
