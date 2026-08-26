from pydantic import BaseModel


class MemberBalanceResponse(BaseModel):
    user_id: int
    name: str
    net_balance: str


class DebtSuggestionResponse(BaseModel):
    from_user_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    amount: str


class GroupBalancesResponse(BaseModel):
    balances: list[MemberBalanceResponse]
    debts: list[DebtSuggestionResponse]