from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_group_member
from app.db.session import get_db_session
from app.models import Expense, User
from app.schemas.expenses import (
    ExpenseResponse,
    ExpenseSortField,
    ExpenseSplitResponse,
    ExpenseUpsertRequest,
    PaginatedExpensesResponse,
    SortDirection,
    SplitType,
)
from app.services.expenses import (
    ExpenseGroupMembershipRequiredError,
    ExpenseMutationForbiddenError,
    ExpenseNotFoundError,
    ExpenseValidationError,
    create_expense,
    delete_expense,
    list_group_expenses,
    update_expense,
)


router = APIRouter(tags=["expenses"])


@router.post(
    "/groups/{group_id}/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_expense_endpoint(
    group_id: int,
    request: ExpenseUpsertRequest,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ExpenseResponse:
    try:
        expense = create_expense(session, group_id, current_user.id, request)
    except ExpenseGroupMembershipRequiredError as error:
        raise _membership_error(error) from error
    except ExpenseValidationError as error:
        raise _validation_error(error) from error
    return _expense_response(expense)


@router.get("/groups/{group_id}/expenses", response_model=PaginatedExpensesResponse)
def list_expenses_endpoint(
    group_id: int,
    current_user: Annotated[User, Depends(require_group_member)],
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort_by: ExpenseSortField = "date",
    sort_order: SortDirection = "desc",
) -> PaginatedExpensesResponse:
    del current_user
    expense_page = list_group_expenses(
        session,
        group_id,
        page,
        page_size,
        sort_by,
        sort_order,
    )
    return PaginatedExpensesResponse(
        items=[_expense_response(expense) for expense in expense_page.expenses],
        page=expense_page.page,
        page_size=expense_page.page_size,
        total=expense_page.total,
        total_pages=(expense_page.total + expense_page.page_size - 1)
        // expense_page.page_size,
    )


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense_endpoint(
    expense_id: int,
    request: ExpenseUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> ExpenseResponse:
    try:
        expense = update_expense(session, expense_id, current_user.id, request)
    except ExpenseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        ) from error
    except ExpenseGroupMembershipRequiredError as error:
        raise _membership_error(error) from error
    except ExpenseMutationForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the expense creator or group owner can edit this expense",
        ) from error
    except ExpenseValidationError as error:
        raise _validation_error(error) from error
    return _expense_response(expense)


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense_endpoint(
    expense_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    try:
        delete_expense(session, expense_id, current_user.id)
    except ExpenseNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        ) from error
    except ExpenseGroupMembershipRequiredError as error:
        raise _membership_error(error) from error
    except ExpenseMutationForbiddenError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the expense creator or group owner can delete this expense",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _expense_response(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        group_id=expense.group_id,
        created_by=expense.created_by,
        description=expense.description,
        amount=expense.amount,
        paid_by=expense.paid_by,
        expense_date=expense.expense_date,
        split_type=SplitType(expense.split_type),
        created_at=expense.created_at,
        updated_at=expense.updated_at,
        splits=[
            ExpenseSplitResponse(user_id=split.user_id, amount=split.amount)
            for split in sorted(expense.splits, key=lambda split: split.user_id)
        ],
    )


def _membership_error(error: ExpenseGroupMembershipRequiredError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not a member of this group",
    )


def _validation_error(error: ExpenseValidationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )
