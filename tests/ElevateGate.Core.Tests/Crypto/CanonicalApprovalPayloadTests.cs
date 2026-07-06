using ElevateGate.Core.Crypto;

namespace ElevateGate.Core.Tests.Crypto;

public class CanonicalApprovalPayloadTests
{
    [Fact]
    public void SameInputs_ProduceIdenticalBytes()
    {
        var expiry = DateTimeOffset.UtcNow;
        var a = CanonicalApprovalPayload.Build("device", "request", "hash", expiry, "nonce");
        var b = CanonicalApprovalPayload.Build("device", "request", "hash", expiry, "nonce");

        Assert.Equal(a, b);
    }

    [Theory]
    [InlineData("deviceX", "request", "hash", "nonce")]
    [InlineData("device", "requestX", "hash", "nonce")]
    [InlineData("device", "request", "hashX", "nonce")]
    [InlineData("device", "request", "hash", "nonceX")]
    public void DifferingField_ProducesDifferentBytes(string deviceId, string requestId, string sha256Hex, string nonce)
    {
        var expiry = DateTimeOffset.UtcNow;
        var baseline = CanonicalApprovalPayload.Build("device", "request", "hash", expiry, "nonce");
        var varied = CanonicalApprovalPayload.Build(deviceId, requestId, sha256Hex, expiry, nonce);

        Assert.NotEqual(baseline, varied);
    }

    [Fact]
    public void FieldBoundaryShifting_CannotForgeCollision()
    {
        // Without length-prefixing, "ab"+"cd" and "a"+"bcd" would concatenate identically.
        var a = CanonicalApprovalPayload.Build("ab", "cd", "hash", DateTimeOffset.UnixEpoch, "nonce");
        var b = CanonicalApprovalPayload.Build("a", "bcd", "hash", DateTimeOffset.UnixEpoch, "nonce");

        Assert.NotEqual(a, b);
    }
}
