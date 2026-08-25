"""Transactional settlement persistence and validation."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Membership, Settlement
from app.services.activities import record_activity
from app.services.balances import calculate_group_balances


class SettlementValidationError(Exception):
    """Raised when a proposed settlement cannot be applied to current balances."""


def create_settlement(
    session: Session,
    group_id: int,
    from_user_id: int,
    to_user_id: int,
    amount: int,
) -> Settlement:
    """Persist one valid payment without changing any derived balance data."""
    if amount <= 0:
        raise SettlementValidationError("Settlement amount must be positive")
    if from_user_id == to_user_id:
        raise SettlementValidationError("Settlement users must be different")

    participant_ids = set(
        session.scalars(
            select(Membership.user_id).where(
                Membership.group_id == group_id,
                Membership.user_id.in_([from_user_id, to_user_id]),
            )
        ).all()
    )
    if participant_ids != {from_user_id, to_user_id}:
        raise SettlementValidationError(
            "Settlement participants must both be members of this group"
        )

    balances = calculate_group_balances(session, group_id)
    payer_balance = balances.balance_for(from_user_id)
    recipient_balance = balances.balance_for(to_user_id)
    if payer_balance >= 0 or recipient_balance <= 0:
        raise SettlementValidationError(
            "The users do not have a settleable balance relationship"
        )

    amount_owed = min(-payer_balance, recipient_balance)
    if amount > amount_owed:
        raise SettlementValidationError(
            "Settlement amount exceeds the amount currently owed"
        )

    settlement = Settlement(
        group_id=group_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        amount=amount,
    )
    session.add(settlement)
    try:
        record_activity(
            session,
            group_id,
            from_user_id,
            "settlement_recorded",
            f"Settlement of {amount} was recorded",
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return get_settlement(session, settlement.id)


def list_group_settlements(session: Session, group_id: int) -> list[Settlement]:
    """Return one group's settlements newest first, with both users populated."""
    return list(
        session.scalars(
            select(Settlement)
            .options(
                joinedload(Settlement.from_user),
                joinedload(Settlement.to_user),
            )
            .where(Settlement.group_id == group_id)
            .order_by(Settlement.created_at.desc(), Settlement.id.desc())
        ).all()
    )


def get_settlement(session: Session, settlement_id: int) -> Settlement:
    settlement = session.scalar(
        select(Settlement)
        .options(
            joinedload(Settlement.from_user),
            joinedload(Settlement.to_user),
        )
        .where(Settlement.id == settlement_id)
    )
    if settlement is None:
        raise RuntimeError("Settlement disappeared after creation")
    return settlement
