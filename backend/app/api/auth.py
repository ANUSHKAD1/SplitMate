from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisteredUserResponse,
    RegistrationRequest,
)
from app.services.auth import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    authenticate_user,
    refresh_user_tokens,
    register_user,
    revoke_refresh_token,
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
        tokens = authenticate_user(session, credentials)
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from error

    return AccessTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: RefreshTokenRequest | None = None,
    session: Session = Depends(get_db_session),
) -> AccessTokenResponse:
    try:
        tokens = refresh_user_tokens(
            session,
            request.refresh_token if request is not None else None,
        )
    except InvalidRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from error

    return AccessTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: RefreshTokenRequest | None = None,
    session: Session = Depends(get_db_session),
) -> None:
    revoke_refresh_token(session, request.refresh_token if request is not None else None)
