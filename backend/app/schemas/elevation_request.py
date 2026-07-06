import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ElevationRequestStatus, SignatureStatus

_SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"


class ElevationRequestCreate(BaseModel):
    """Submitted by an authenticated device. Every field describes a fact the agent already
    derived locally (file hash, signature status, etc.) - the backend does not re-derive these,
    but it does strictly validate their shape."""

    username: str = Field(min_length=1, max_length=255)
    filename: str = Field(min_length=1, max_length=500)
    canonical_path: str = Field(min_length=1, max_length=32768)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    publisher: str | None = Field(default=None, max_length=500)
    signature_status: SignatureStatus
    file_size: int = Field(ge=0)
    file_version: str | None = Field(default=None, max_length=100)
    reason: str = Field(min_length=5, max_length=4000)

    @field_validator("sha256")
    @classmethod
    def _lowercase_sha256(cls, value: str) -> str:
        return value.lower()


class ElevationRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_uuid: uuid.UUID
    device_id: int
    # Sourced from the joined Device row (see ElevationRequest.device_uuid/device_hostname
    # properties) - added for the ElevateGate Dashboard, which needs to display the device
    # without a separate lookup by device_id on every row.
    device_uuid: uuid.UUID
    device_hostname: str
    # Null when submitted via the agent-compatible route - the .NET agent never captures the
    # local Windows username. See docs/API_CONTRACT.md.
    username: str | None
    filename: str
    canonical_path: str
    sha256: str
    publisher: str | None
    signature_status: SignatureStatus
    file_size: int
    file_version: str | None
    reason: str
    status: ElevationRequestStatus
    requested_at: datetime
    reviewed_at: datetime | None
    reviewed_by: int | None
    expires_at: datetime


class ElevationRequestList(BaseModel):
    items: list[ElevationRequestRead]
    total: int


class DenyRequest(BaseModel):
    """Optional free-text reason, recorded only in the audit log metadata (ElevationRequest has
    no dedicated denial-reason column per the specified schema)."""

    reason: str | None = Field(default=None, max_length=2000)
