from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.config import get_settings
from app.models.admin_user import AdminUser
from app.models.enums import ElevationRequestStatus
from app.repositories import device_repository, elevation_request_repository
from app.schemas.alert import Alert, AlertList, AlertSeverity, AlertType
from app.schemas.dashboard import DashboardSummary, EnrollmentInfo

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Below this fraction of free disk space, a device is flagged critical.
_LOW_DISK_FREE_RATIO = 0.10
# Above this fraction of RAM in use, a device is flagged as a warning (not critical - high RAM
# usage alone is common and often transient, unlike running out of disk space).
_HIGH_RAM_USAGE_RATIO = 0.90


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


@router.get("/alerts", response_model=AlertList)
async def get_dashboard_alerts(
    _admin: AdminUser = Depends(require_role("admin", "reviewer")),
    session: AsyncSession = Depends(get_db),
) -> AlertList:
    """
    Computed fresh on every call from current device state - no separate alerts table, nothing to
    silently go stale. Three checks, in order of severity: low disk space and offline are
    critical; high RAM usage is a warning. A device only ever produces the offline alert if it has
    checked in at least once before (last_seen is not None) - a device that's never sent a
    heartbeat isn't "offline," it just hasn't reported yet.
    """
    settings = get_settings()
    online_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.device_online_threshold_seconds)

    devices = await device_repository.list_active(session)
    alerts: list[Alert] = []

    for device in devices:
        if device.disk_total_bytes and device.disk_total_bytes > 0 and device.disk_free_bytes is not None:
            free_ratio = device.disk_free_bytes / device.disk_total_bytes
            if free_ratio < _LOW_DISK_FREE_RATIO:
                alerts.append(
                    Alert(
                        severity=AlertSeverity.CRITICAL,
                        type=AlertType.LOW_DISK_SPACE,
                        device_id=device.id,
                        device_uuid=str(device.device_uuid),
                        hostname=device.hostname,
                        message=f"Only {free_ratio:.0%} disk space free "
                        f"({device.disk_free_bytes / (1024**3):.1f} GB of "
                        f"{device.disk_total_bytes / (1024**3):.1f} GB).",
                    )
                )

        if device.ram_total_bytes and device.ram_total_bytes > 0 and device.ram_used_bytes is not None:
            used_ratio = device.ram_used_bytes / device.ram_total_bytes
            if used_ratio > _HIGH_RAM_USAGE_RATIO:
                alerts.append(
                    Alert(
                        severity=AlertSeverity.WARNING,
                        type=AlertType.HIGH_RAM_USAGE,
                        device_id=device.id,
                        device_uuid=str(device.device_uuid),
                        hostname=device.hostname,
                        message=f"RAM usage at {used_ratio:.0%}.",
                    )
                )

        if device.last_seen is not None and device.last_seen < online_cutoff:
            alerts.append(
                Alert(
                    severity=AlertSeverity.CRITICAL,
                    type=AlertType.DEVICE_OFFLINE,
                    device_id=device.id,
                    device_uuid=str(device.device_uuid),
                    hostname=device.hostname,
                    message=f"Last seen {device.last_seen.isoformat()}.",
                )
            )

    return AlertList(items=alerts, total=len(alerts))


@router.get("/enrollment-info", response_model=EnrollmentInfo)
async def get_enrollment_info(
    _admin: AdminUser = Depends(require_role("admin")),
) -> EnrollmentInfo:
    """Admin-only (not "reviewer" - see EnrollmentInfo). Lets the dashboard show the enrollment
    key and a ready-to-copy install command without anyone needing shell access to the server."""
    settings = get_settings()
    return EnrollmentInfo(
        enrollment_key=settings.enrollment_key,
        install_command="irm https://raw.githubusercontent.com/buildwithmg/Elevategate/main/install.ps1 | iex",
    )
