from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RegisteredUserResponse,
    RegistrationRequest,
)
from app.services.auth import (
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)


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


@router.post("/login", response_model=AccessTokenResponse)
def login(
    credentials: LoginRequest,
    session: Session = Depends(get_db_session),
) -> AccessTokenResponse:
    try:
        access_token = authenticate_user(session, credentials)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from error

    return AccessTokenResponse(access_token=access_token)
