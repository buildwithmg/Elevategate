namespace ElevateGate.Core.Models;

public sealed record EnrollmentRequest(string DeviceId, string MachineName, string OperatingSystemVersion);

/// <summary>
/// Note: the server's Ed25519 public key is deliberately NOT part of the enrollment response.
/// It is pinned into the service's configuration at deployment time so an attacker positioned
/// during enrollment can never substitute their own signing key (see THREAT_MODEL.md).
/// </summary>
public sealed record EnrollmentResult(string BearerToken, DateTimeOffset EnrolledAtUtc);

public sealed record ApprovalDecision(string RequestId, RequestStatus Status, ApprovalToken? Token);
