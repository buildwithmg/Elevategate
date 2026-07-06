namespace ElevateGate.Core.Validation;

public readonly record struct PathValidationOutcome(bool IsValid, string? CanonicalPath, PathRejectionReason Reason)
{
    public static PathValidationOutcome Valid(string canonicalPath) =>
        new(true, canonicalPath, PathRejectionReason.None);

    public static PathValidationOutcome Invalid(PathRejectionReason reason) =>
        new(false, null, reason);
}
