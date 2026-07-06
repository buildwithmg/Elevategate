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
        )


class DeviceList(BaseModel):
    items: list[DeviceRead]
    total: int
