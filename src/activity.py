from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Article, DailyActivity
from .utils import utcnow


def current_starred_count(session: Session) -> int:
    return session.scalar(select(func.count(Article.id)).where(Article.is_starred == 1)) or 0


def record_today_visit(session: Session, increment_visit: bool = True) -> None:
    today = date.today().isoformat()
    activity = session.execute(select(DailyActivity).where(DailyActivity.activity_date == today)).scalar_one_or_none()
    if activity is None:
        activity = DailyActivity(activity_date=today, visit_count=0)
        session.add(activity)
    if increment_visit:
        activity.visit_count += 1
    activity.starred_count = current_starred_count(session)
    activity.updated_at = utcnow()
    session.commit()


def refresh_today_starred_count(session: Session) -> None:
    record_today_visit(session, increment_visit=False)


def load_activity_days(session: Session, days: int = 30) -> dict[str, DailyActivity]:
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = session.execute(select(DailyActivity).where(DailyActivity.activity_date >= start)).scalars()
    return {row.activity_date: row for row in rows}
