using ElevateGate.Core.Crypto;
using ElevateGate.Core.Models;

namespace ElevateGate.Core.Tests.TestSupport;

/// <summary>Builds validly-signed <see cref="ApprovalToken"/>s for tests, standing in for the future backend's signer.</summary>
public sealed class ApprovalTokenTestFactory
{
    public byte[] PublicKey { get; }
    private readonly byte[] _privateKey;

    public ApprovalTokenTestFactory()
    {
        (PublicKey, _privateKey) = Ed25519KeyPairGenerator.Generate();
    }

    public ApprovalToken CreateValid(
        string deviceId = "device-1",
        string requestId = "request-1",
        string sha256Hex = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        DateTimeOffset? expiresAtUtc = null,
        string nonce = "nonce-1")
    {
        var expiry = expiresAtUtc ?? DateTimeOffset.UtcNow.AddMinutes(15);
        var payload = CanonicalApprovalPayload.Build(deviceId, requestId, sha256Hex, expiry, nonce);
        var signature = Ed25519KeyPairGenerator.Sign(_privateKey, payload);
        return new ApprovalToken(deviceId, requestId, sha256Hex, expiry, nonce, signature);
    }
}
