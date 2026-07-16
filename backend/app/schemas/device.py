import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EnrollmentStatus


class DeviceEnrollRequest(BaseModel):
    device_uuid: uuid.UUID
    hostname: str = Field(min_length=1, max_length=255)
    operating_system: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(min_length=1, max_length=50)


class DeviceEnrollResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_uuid: uuid.UUID
    # Shown exactly once, here, at enrollment. Only its Argon2id hash is ever persisted.
    device_secret: str
    enrollment_status: EnrollmentStatus
    created_at: datetime


class DeviceHeartbeatRequest(BaseModel):
    agent_version: str | None = Field(default=None, max_length=50)


class DeviceHeartbeatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_uuid: uuid.UUID
    last_seen: datetime
    enrollment_status: EnrollmentStatus


class DeviceRead(BaseModel):
    id: int
    device_uuid: uuid.UUID
    hostname: str
    operating_system: str
    agent_version: str | None
    last_seen: datetime | None
    enrollment_status: EnrollmentStatus
    # Server-computed (enrollment_status == active AND last_seen within
    # settings.device_online_threshold_seconds) - never derived client-side, so the "is this
    # device online" business rule lives in exactly one place.
    online: bool
    created_at: datetime
    group_id: int | None
    group_name: str | None
    disk_total_bytes: int | None
    disk_free_bytes: int | None
    ram_total_bytes: int | None
    ram_used_bytes: int | None
    last_telemetry_at: datetime | None
    # True iff an admin asked for an update and the agent hasn't yet reported back a newer
    # agent_version since then - see POST /api/v1/devices/{id}/request-update.
    update_requested: bool

    @classmethod
    def from_device(cls, device, *, online: bool) -> "DeviceRead":
        return cls(
            id=device.id,
            device_uuid=device.device_uuid,
            hostname=device.hostname,
            operating_system=device.operating_system,
            agent_version=device.agent_version,
            last_seen=device.last_seen,
            enrollment_status=device.enrollment_status,
            online=online,
            created_at=device.created_at,
            group_id=device.group_id,
            group_name=device.group.name if device.group else None,
            disk_total_bytes=device.disk_total_bytes,
            disk_free_bytes=device.disk_free_bytes,
            ram_total_bytes=device.ram_total_bytes,
            ram_used_bytes=device.ram_used_bytes,
            last_telemetry_at=device.last_telemetry_at,
            update_requested=device.update_requested_at is not None,
        )


class DeviceList(BaseModel):
    items: list[DeviceRead]
    total: int
