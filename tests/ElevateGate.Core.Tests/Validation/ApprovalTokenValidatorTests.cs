using ElevateGate.Core.Tests.TestSupport;
using ElevateGate.Core.Validation;

namespace ElevateGate.Core.Tests.Validation;

public class ApprovalTokenValidatorTests
{
    private const string DeviceId = "device-1";
    private const string RequestId = "request-1";
    private const string Sha256Hex = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

    private static ApprovalTokenValidator CreateValidator(
        ApprovalTokenTestFactory factory, out InMemoryNonceStore nonceStore, FakeTimeProvider? timeProvider = null)
    {
        nonceStore = new InMemoryNonceStore();
        return new ApprovalTokenValidator(factory.PublicKey, nonceStore, timeProvider);
    }

    [Fact]
    public async Task ValidToken_IsAccepted()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);

        var outcome = await validator.ValidateAsync(token, DeviceId, RequestId, Sha256Hex);

        Assert.True(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.None, outcome.Reason);
    }

    [Fact]
    public async Task ExpiredToken_IsRejected()
    {
        var factory = new ApprovalTokenTestFactory();
        var timeProvider = new FakeTimeProvider(DateTimeOffset.UtcNow);
        var validator = CreateValidator(factory, out _, timeProvider);
        var token = factory.CreateValid(
            deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex,
            expiresAtUtc: timeProvider.GetUtcNow().AddMinutes(-1));

        var outcome = await validator.ValidateAsync(token, DeviceId, RequestId, Sha256Hex);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.Expired, outcome.Reason);
    }

    [Fact]
    public async Task ReusedNonce_IsRejectedOnSecondAttempt()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex, nonce: "nonce-reuse");

        var first = await validator.ValidateAsync(token, DeviceId, RequestId, Sha256Hex);
        var second = await validator.ValidateAsync(token, DeviceId, RequestId, Sha256Hex);

        Assert.True(first.IsValid);
        Assert.False(second.IsValid);
        Assert.Equal(ApprovalRejectionReason.NonceReused, second.Reason);
    }

    [Fact]
    public async Task HashMismatch_IsRejected()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);
        var differentFileHash = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

        var outcome = await validator.ValidateAsync(token, DeviceId, RequestId, differentFileHash);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.HashMismatch, outcome.Reason);
    }

    [Fact]
    public async Task DeviceMismatch_IsRejected()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);

        var outcome = await validator.ValidateAsync(token, "some-other-device", RequestId, Sha256Hex);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.DeviceMismatch, outcome.Reason);
    }

    [Fact]
    public async Task RequestIdMismatch_IsRejected()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);

        var outcome = await validator.ValidateAsync(token, DeviceId, "some-other-request", Sha256Hex);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.RequestIdMismatch, outcome.Reason);
    }

    [Fact]
    public async Task TokenForOneRequest_CannotExecuteADifferentRequest_EvenWithTheSameFileHash()
    {
        // Two separate pending requests on the same device happen to reference identical file
        // content (e.g. the same installer requested twice under different reasons). A token
        // legitimately signed for "request-a" must never authorize executing "request-b", even
        // though both share the same SHA-256.
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var tokenForRequestA = factory.CreateValid(deviceId: DeviceId, requestId: "request-a", sha256Hex: Sha256Hex);

        var outcome = await validator.ValidateAsync(tokenForRequestA, DeviceId, "request-b", Sha256Hex);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.RequestIdMismatch, outcome.Reason);
    }

    [Fact]
    public async Task TamperedSignature_IsRejected()
    {
        var factory = new ApprovalTokenTestFactory();
        var validator = CreateValidator(factory, out _);
        var token = factory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);
        var tampered = token with { Sha256Hex = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" };

        var outcome = await validator.ValidateAsync(
            tampered, DeviceId, RequestId, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc");

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.InvalidSignature, outcome.Reason);
    }

    [Fact]
    public async Task WrongSigningKey_IsRejected()
    {
        var legitimateFactory = new ApprovalTokenTestFactory();
        var attackerFactory = new ApprovalTokenTestFactory();
        // Validator trusts the legitimate server's key, but the token is signed by a different key.
        var validator = CreateValidator(legitimateFactory, out _);
        var forgedToken = attackerFactory.CreateValid(deviceId: DeviceId, requestId: RequestId, sha256Hex: Sha256Hex);

        var outcome = await validator.ValidateAsync(forgedToken, DeviceId, RequestId, Sha256Hex);

        Assert.False(outcome.IsValid);
        Assert.Equal(ApprovalRejectionReason.InvalidSignature, outcome.Reason);
    }
}
