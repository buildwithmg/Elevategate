namespace ElevateGate.Core.Models;

/// <summary>
/// A signed decision from the backend. Authorizes exactly one execution of exactly one file
/// (bound by <see cref="Sha256Hex"/>) on exactly one device, once, before <see cref="ExpiresAtUtc"/>.
/// </summary>
public sealed record ApprovalToken(
    string DeviceId,
    string RequestId,
    string Sha256Hex,
    DateTimeOffset ExpiresAtUtc,
    string Nonce,
    byte[] Signature);
