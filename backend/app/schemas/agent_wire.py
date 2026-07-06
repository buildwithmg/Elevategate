"""
Wire schemas for the three endpoints the real .NET agent actually calls
(ElevateGate.Infrastructure.Api.HttpApprovalApiClient): POST /api/v1/enroll,
POST /api/v1/requests, GET /api/v1/devices/{deviceId}/decisions.

The agent serializes with `JsonSerializerDefaults.Web` (camelCase) and a plain
`JsonStringEnumConverter(JsonNamingPolicy.CamelCase)` for enums - every model here mirrors an
actual C# record in ElevateGate.Core.Models field-for-field, including casing, so no translation
layer is needed on the agent side. See docs/API_CONTRACT.md.
"""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import ElevationRequestStatus, SignatureStatus

_SHA256_PATTERN = r"^[0-9a-fA-F]{64}$"


class AgentCamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AgentEnrollRequest(AgentCamelModel):
    """Mirrors ElevateGate.Core.Models.EnrollmentRequest(DeviceId, MachineName, OperatingSystemVersion)."""

    device_id: uuid.UUID
    machine_name: str = Field(min_length=1, max_length=255)
    operating_system_version: str = Field(min_length=1, max_length=255)


class AgentEnrollResponse(AgentCamelModel):
    """Mirrors EnrollmentResult(BearerToken, EnrolledAtUtc). Deliberately does not include the
    server's Ed25519 public key - see ElevateGate's THREAT_MODEL.md: it's pinned into the agent's
    own configuration at deployment time, never learned from the enrollment response."""

    bearer_token: str
    enrolled_at_utc: datetime


class AgentSignatureTrustStatus(str, Enum):
    """Wire values match .NET's JsonStringEnumConverter(JsonNamingPolicy.CamelCase) output for
    SignatureTrustStatus exactly - note `hashMismatch`, which differs from this backend's
    internal SignatureStatus.HASH_MISMATCH ("hash_mismatch")."""

    UNSIGNED = "unsigned"
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    HASH_MISMATCH = "hashMismatch"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


_AGENT_TO_INTERNAL_SIGNATURE_STATUS: dict[AgentSignatureTrustStatus, SignatureStatus] = {
    AgentSignatureTrustStatus.UNSIGNED: SignatureStatus.UNSIGNED,
    AgentSignatureTrustStatus.TRUSTED: SignatureStatus.TRUSTED,
    AgentSignatureTrustStatus.UNTRUSTED: SignatureStatus.UNTRUSTED,
    AgentSignatureTrustStatus.HASH_MISMATCH: SignatureStatus.HASH_MISMATCH,
    AgentSignatureTrustStatus.REVOKED: SignatureStatus.REVOKED,
    AgentSignatureTrustStatus.UNKNOWN: SignatureStatus.UNKNOWN,
}


def to_internal_signature_status(value: AgentSignatureTrustStatus) -> SignatureStatus:
    return _AGENT_TO_INTERNAL_SIGNATURE_STATUS[value]


class AgentFileMetadata(AgentCamelModel):
    """Mirrors FileMetadata(FileName, FullPath, SizeBytes, FileVersion, Sha256Hex)."""

    file_name: str = Field(min_length=1, max_length=500)
    full_path: str = Field(min_length=1, max_length=32768)
    size_bytes: int = Field(ge=0)
    file_version: str | None = Field(default=None, max_length=100)
    sha256_hex: str = Field(pattern=_SHA256_PATTERN)


class AgentSignatureInfo(AgentCamelModel):
    """Mirrors SignatureInfo(TrustStatus, PublisherCommonName, CertificateThumbprint)."""

    trust_status: AgentSignatureTrustStatus
    publisher_common_name: str | None = Field(default=None, max_length=500)
    certificate_thumbprint: str | None = Field(default=None, max_length=255)


class AgentApprovalRequest(AgentCamelModel):
    """Mirrors ApprovalRequest(RequestId, DeviceId, File, Signature, Reason, RequestedAtUtc) -
    what the agent POSTs to /api/v1/requests. The agent generates RequestId itself and never
    reads the response body, so this id must be preserved verbatim as the elevation request's
    request_uuid."""

    request_id: uuid.UUID
    device_id: uuid.UUID
    file: AgentFileMetadata
    signature: AgentSignatureInfo
    reason: str = Field(min_length=5, max_length=4000)
    requested_at_utc: datetime


class AgentApprovalToken(AgentCamelModel):
    """Mirrors ApprovalToken(DeviceId, RequestId, Sha256Hex, ExpiresAtUtc, Nonce, Signature).
    `signature` is base64 text - System.Text.Json deserializes a byte[] property from a base64
    JSON string natively, no custom converter needed on the agent side."""

    device_id: uuid.UUID
    request_id: uuid.UUID
    sha256_hex: str
    expires_at_utc: datetime
    nonce: str
    signature: str


class AgentApprovalDecision(AgentCamelModel):
    """Mirrors ApprovalDecision(RequestId, Status, Token). `status`'s wire values
    (pending/approved/denied/expired) already coincide with ElevationRequestStatus's own values,
    so no camelCase enum translation is needed here - only `SignatureTrustStatus.hashMismatch`
    (above) actually differs from this backend's internal enum spelling."""

    request_id: uuid.UUID
    status: ElevationRequestStatus
    token: AgentApprovalToken | None
