from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import RegisteredUserResponse, RegistrationRequest
from app.services.auth import DuplicateEmailError, register_user


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=RegisteredUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    registration: RegistrationRequest,
    session: Session = Depends(get_db_session),
) -> RegisteredUserResponse:
    try:
        return register_user(session, registration)
    except DuplicateEmailError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from error
