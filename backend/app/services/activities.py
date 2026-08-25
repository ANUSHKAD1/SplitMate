"""Reusable, internal activity-log recording and retrieval."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity
from app.realtime.events import emit_group_event


@dataclass(frozen=True)
class ActivityPage:
    activities: list[Activity]
    total: int
    page: int
    page_size: int


def record_activity(
    session: Session,
    group_id: int,
    user_id: int,
    event_type: str,
    message: str,
) -> Activity:
    """Stage an activity row in the caller's transaction without committing it."""
    activity = Activity(
        group_id=group_id,
        user_id=user_id,
        event_type=event_type,
        message=message,
    )
    session.add(activity)
    return activity


def publish_activity_added(activity: Activity) -> None:
    """Emit a post-commit notification for an already-persisted activity row."""
    emit_group_event(
        activity.group_id,
        "activity_added",
        {"activity_id": activity.id, "event_type": activity.event_type},
    )


def list_group_activities(
    session: Session,
    group_id: int,
    page: int,
    page_size: int,
) -> ActivityPage:
    """Fetch one group-scoped activity page in newest-first database order."""
    total = int(
        session.scalar(
            select(func.count(Activity.id)).where(Activity.group_id == group_id)
        )
        or 0
    )
    activities = list(
        session.scalars(
            select(Activity)
            .where(Activity.group_id == group_id)
            .order_by(Activity.created_at.desc(), Activity.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return ActivityPage(
        activities=activities,
        total=total,
        page=page,
        page_size=page_size,
    )
