from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection


router = APIRouter(tags=["health"])


@router.get("/health")
def api_health() -> dict[str, str]:
    return {"status": "ok", "message": "SplitMate API is running"}


@router.get("/health/db")
def database_health() -> dict[str, str]:
    try:
        check_database_connection()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error

    return {"status": "ok", "database": "connected"}
