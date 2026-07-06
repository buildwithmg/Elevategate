import uuid

from pydantic import BaseModel

from app.models.enums import ElevationRequestStatus
from app.schemas.approval import ApprovalRead


class DecisionRead(BaseModel):
    request_uuid: uuid.UUID
    status: ElevationRequestStatus
    approval: ApprovalRead | None
