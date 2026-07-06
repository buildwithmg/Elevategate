namespace ElevateGate.Core.Validation;

/// <summary>
/// The single authority for deciding whether a candidate file path is allowed to be executed.
/// Called by the service on every request — never trusts a path supplied by the tray beyond
/// treating it as a starting point to re-validate from scratch.
/// </summary>
public sealed class PathValidator
{
    private readonly IDriveClassifier _driveClassifier;

    public PathValidator(IDriveClassifier driveClassifier)
    {
        _driveClassifier = driveClassifier;
    }

    public PathValidationOutcome Validate(string rawPath)
    {
        if (string.IsNullOrWhiteSpace(rawPath))
            return PathValidationOutcome.Invalid(PathRejectionReason.Malformed);

        if (WindowsPathRules.IsUncOrDeviceLiteral(rawPath))
            return PathValidationOutcome.Invalid(PathRejectionReason.UncOrNetworkPath);

        if (WindowsPathRules.ContainsTraversalSegment(rawPath))
            return PathValidationOutcome.Invalid(PathRejectionReason.Traversal);

        if (!WindowsPathRules.TryCanonicalize(rawPath, out var canonicalPath))
            return PathValidationOutcome.Invalid(PathRejectionReason.Malformed);

        var driveRoot = WindowsPathRules.GetDriveRoot(canonicalPath);
        var classification = _driveClassifier.Classify(driveRoot);

        // Deny by default: only a drive positively identified as Fixed is allowed. Anything the
        // classifier can't confirm (CD-ROM, RAM disk, unrecognized) is rejected rather than
        // assumed safe.
        return classification switch
        {
            DriveClassification.Fixed => PathValidationOutcome.Valid(canonicalPath),
            DriveClassification.Network => PathValidationOutcome.Invalid(PathRejectionReason.UncOrNetworkPath),
            DriveClassification.Removable => PathValidationOutcome.Invalid(PathRejectionReason.RemovableDrive),
            _ => PathValidationOutcome.Invalid(PathRejectionReason.UnsupportedDrive),
        };
    }
}
