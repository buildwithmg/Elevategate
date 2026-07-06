namespace ElevateGate.Core.Validation;

public enum PathRejectionReason
{
    None,
    Malformed,
    Traversal,
    UncOrNetworkPath,
    RemovableDrive,
    UnsupportedDrive,
}
