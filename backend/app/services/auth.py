from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.schemas.auth import RegistrationRequest


class DuplicateEmailError(Exception):
    """Raised when a user attempts to register an existing email address."""


def register_user(session: Session, registration: RegistrationRequest) -> User:
    existing_user = session.scalar(
        select(User.id).where(User.email == registration.email)
    )
    if existing_user is not None:
        raise DuplicateEmailError

    user = User(
        name=registration.name,
        email=registration.email,
        password_hash=hash_password(registration.password),
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DuplicateEmailError from error

    session.refresh(user)
    return user
