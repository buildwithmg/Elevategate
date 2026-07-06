import enum


class AdminRole(str, enum.Enum):
    ADMIN = "admin"
    REVIEWER = "reviewer"


class EnrollmentStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"


class SignatureStatus(str, enum.Enum):
    """Mirrors the agent's SignatureTrustStatus (ElevateGate.Core.Models.SignatureInfo)."""

    UNSIGNED = "unsigned"
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    HASH_MISMATCH = "hash_mismatch"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class ElevationRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalAction(str, enum.Enum):
    """What an issued Approval authorizes. A single value today; the column exists so new
    action types (e.g. a future distinct install-with-elevated-context action) don't require a
    schema change."""

    EXECUTE = "execute"


class ActorType(str, enum.Enum):
    ADMIN = "admin"
    DEVICE = "device"
    SYSTEM = "system"
