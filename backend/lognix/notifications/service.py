from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lognix.notifications.models import Notification, NotificationStatus, NotificationType


async def notify(
    db: AsyncSession,
    type_: NotificationType,
    title: str,
    *,
    host_id: uuid.UUID | None = None,
    container_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    dedupe: bool = True,
) -> Notification | None:
    """Cria uma notificação. Com dedupe, não repete uma `new` igual (tipo + host + container)."""
    if dedupe:
        stmt = select(Notification).where(
            Notification.type == type_,
            Notification.status == NotificationStatus.new,
            Notification.host_id == host_id,
            Notification.container_id == container_id,
        )
        if (await db.execute(stmt)).scalars().first() is not None:
            return None
    n = Notification(
        type=type_, title=title, host_id=host_id, container_id=container_id, payload=payload or {}
    )
    db.add(n)
    await db.flush()
    return n


async def list_new(db: AsyncSession, limit: int = 200) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.status == NotificationStatus.new)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars())


async def list_history(db: AsyncSession, limit: int = 200) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.status == NotificationStatus.seen)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars())


async def count_new(db: AsyncSession) -> int:
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.status == NotificationStatus.new)
    )
    return int((await db.execute(stmt)).scalar_one())


async def mark_seen(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    n = await db.get(Notification, notification_id)
    if n is None:
        return False
    n.status = NotificationStatus.seen
    n.seen_by = user_id
    n.seen_at = datetime.now(UTC)
    await db.commit()
    return True


async def mark_all_seen(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.status == NotificationStatus.new)
        .values(status=NotificationStatus.seen, seen_by=user_id, seen_at=datetime.now(UTC))
    )
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
