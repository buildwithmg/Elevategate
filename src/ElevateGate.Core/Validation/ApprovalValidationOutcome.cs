namespace ElevateGate.Core.Validation;

public readonly record struct ApprovalValidationOutcome(bool IsValid, ApprovalRejectionReason Reason)
{
    public static ApprovalValidationOutcome Valid() => new(true, ApprovalRejectionReason.None);

    public static ApprovalValidationOutcome Invalid(ApprovalRejectionReason reason) => new(false, reason);
}
