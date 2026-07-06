namespace ElevateGate.Core.Models;

/// <summary>What the service submits to the backend to ask for a decision. All fields are derived server-side.</summary>
public sealed record ApprovalRequest(
    string RequestId,
    string DeviceId,
    FileMetadata File,
    SignatureInfo Signature,
    string Reason,
    DateTimeOffset RequestedAtUtc);
