from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel

from lognix.auth.deps import CurrentUser, DbSession
from lognix.errors import ApiError
from lognix.notifications import service
from lognix.notifications.models import NotificationStatus, NotificationType

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    host_id: uuid.UUID | None
    container_id: uuid.UUID | None
    title: str
    payload: dict[str, Any]
    status: NotificationStatus
    created_at: datetime
    seen_at: datetime | None

    model_config = {"from_attributes": True}


class CountOut(BaseModel):
    new: int


class SeenAllOut(BaseModel):
    marked: int


@router.get("", response_model=list[NotificationOut])
async def list_new(_: CurrentUser, db: DbSession) -> list[NotificationOut]:
    return [NotificationOut.model_validate(n) for n in await service.list_new(db)]


@router.get("/history", response_model=list[NotificationOut])
async def list_history(_: CurrentUser, db: DbSession) -> list[NotificationOut]:
    return [NotificationOut.model_validate(n) for n in await service.list_history(db)]


@router.get("/count", response_model=CountOut)
async def count(_: CurrentUser, db: DbSession) -> CountOut:
    return CountOut(new=await service.count_new(db))


@router.post("/{notification_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
async def seen(notification_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    if not await service.mark_seen(db, notification_id, user.id):
        raise ApiError(404, "not_found", "Notificação não encontrada.")


@router.post("/seen-all", response_model=SeenAllOut)
async def seen_all(user: CurrentUser, db: DbSession) -> SeenAllOut:
    return SeenAllOut(marked=await service.mark_all_seen(db, user.id))
