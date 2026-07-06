namespace ElevateGate.Core.Validation;

public enum ApprovalRejectionReason
{
    None,
    InvalidSignature,
    DeviceMismatch,
    RequestIdMismatch,
    Expired,
    NonceReused,
    HashMismatch,
}
