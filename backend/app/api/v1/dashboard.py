from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.config import get_settings
from app.models.admin_user import AdminUser
from app.models.enums import ElevationRequestStatus
from app.repositories import device_repository, elevation_request_repository
from app.schemas.dashboard import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _start_of_today_utc(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    today_start = _start_of_today_utc(now)
    online_cutoff = now - timedelta(seconds=settings.device_online_threshold_seconds)

    pending = await elevation_request_repository.count_pending(session)
    approved_today = await elevation_request_repository.count_reviewed_since(
        session, status_filter=ElevationRequestStatus.APPROVED, since=today_start
    )
    denied_today = await elevation_request_repository.count_reviewed_since(
        session, status_filter=ElevationRequestStatus.DENIED, since=today_start
    )
    active_devices, offline_devices = await device_repository.count_online_offline(
        session, online_cutoff=online_cutoff
    )

    return DashboardSummary(
        pending_requests=pending,
        approved_today=approved_today,
        denied_today=denied_today,
        active_devices=active_devices,
        offline_devices=offline_devices,
    )
