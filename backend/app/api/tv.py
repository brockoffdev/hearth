"""Anonymous TV snapshot endpoint — Phase 9 Task A.

Intentionally has no auth dependency: the TV wall display is accessible to
anyone on the LAN, consistent with spec §10's "Open on the LAN" decision.
Operators who need stricter access control should add network-level protection.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.base import get_db
from backend.app.db.models import Event, FamilyMember

router = APIRouter()

_EXCLUDED_STATUSES = {"rejected", "superseded"}


class TvFamilyMember(BaseModel):
    id: int
    name: str
    color_hex: str


class TvEvent(BaseModel):
    id: int
    title: str
    start_dt: datetime
    end_dt: datetime | None
    all_day: bool
    family_member_id: int | None
    family_member_name: str | None
    family_member_color_hex: str | None


class TvSnapshotResponse(BaseModel):
    family_members: list[TvFamilyMember]
    events: list[TvEvent]
    server_time: datetime


@router.get("/snapshot")
async def get_tv_snapshot(db: AsyncSession = Depends(get_db)) -> TvSnapshotResponse:
    members_result = await db.execute(
        select(FamilyMember).order_by(FamilyMember.sort_order)
    )
    members = list(members_result.scalars().all())
    members_by_id = {m.id: m for m in members}

    events_result = await db.execute(
        select(Event)
        .where(Event.status.not_in(list(_EXCLUDED_STATUSES)))
        .order_by(Event.start_dt.asc())
    )
    events = list(events_result.scalars().all())

    tv_members = [
        TvFamilyMember(id=m.id, name=m.name, color_hex=m.color_hex_center)
        for m in members
    ]

    tv_events = [
        TvEvent(
            id=e.id,
            title=e.title,
            start_dt=e.start_dt,
            end_dt=e.end_dt,
            all_day=e.all_day,
            family_member_id=e.family_member_id,
            family_member_name=(
                members_by_id[e.family_member_id].name
                if e.family_member_id and e.family_member_id in members_by_id
                else None
            ),
            family_member_color_hex=(
                members_by_id[e.family_member_id].color_hex_center
                if e.family_member_id and e.family_member_id in members_by_id
                else None
            ),
        )
        for e in events
    ]

    return TvSnapshotResponse(
        family_members=tv_members,
        events=tv_events,
        server_time=datetime.now(UTC),
    )
