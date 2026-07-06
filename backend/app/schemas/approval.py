import base64
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import ApprovalAction


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    elevation_request_id: int
    action: ApprovalAction
    device_uuid: uuid.UUID
    sha256: str
    nonce: str
    issued_at: datetime
    expires_at: datetime
    signature: str
    consumed_at: datetime | None

    @field_validator("signature", mode="before")
    @classmethod
    def _encode_signature(cls, value: object) -> str:
        if isinstance(value, (bytes, bytearray)):
            return base64.b64encode(bytes(value)).decode("ascii")
        return value  # already a string (e.g. constructed directly in a test)


class ConsumedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    elevation_request_id: int
    consumed_at: datetime
