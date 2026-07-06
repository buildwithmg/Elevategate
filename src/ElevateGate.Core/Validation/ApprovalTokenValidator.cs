using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Crypto;
using ElevateGate.Core.Models;

namespace ElevateGate.Core.Validation;

/// <summary>
/// The single gate a decision must pass through before the service will ever launch a process.
/// Every rejection path is a distinct, logged, testable outcome — nothing here silently
/// "assumes valid" or short-circuits into an approval.
/// </summary>
public sealed class ApprovalTokenValidator
{
    private readonly byte[] _serverPublicKey;
    private readonly INonceStore _nonceStore;
    private readonly TimeProvider _timeProvider;
    private readonly Ed25519Verifier _verifier;

    public ApprovalTokenValidator(
        byte[] serverPublicKey,
        INonceStore nonceStore,
        TimeProvider? timeProvider = null,
        Ed25519Verifier? verifier = null)
    {
        ArgumentNullException.ThrowIfNull(serverPublicKey);
        ArgumentNullException.ThrowIfNull(nonceStore);
        _serverPublicKey = serverPublicKey;
        _nonceStore = nonceStore;
        _timeProvider = timeProvider ?? TimeProvider.System;
        _verifier = verifier ?? new Ed25519Verifier();
    }

    /// <summary>
    /// Validates a token for immediate execution. <paramref name="currentFileSha256Hex"/> must be
    /// freshly computed by the caller from the file on disk right now — never a cached value.
    /// <paramref name="expectedRequestId"/> must be the id of the specific request this token is
    /// about to be used to execute — not merely "some pending request on this device" — so a
    /// token can never be cross-applied to a different request that happens to reference a file
    /// with the same content (and therefore the same SHA-256).
    /// </summary>
    public async Task<ApprovalValidationOutcome> ValidateAsync(
        ApprovalToken token,
        string expectedDeviceId,
        string expectedRequestId,
        string currentFileSha256Hex,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(token);

        var payload = CanonicalApprovalPayload.Build(
            token.DeviceId, token.RequestId, token.Sha256Hex, token.ExpiresAtUtc, token.Nonce);

        if (!_verifier.Verify(_serverPublicKey, payload, token.Signature))
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.InvalidSignature);

        if (!string.Equals(token.DeviceId, expectedDeviceId, StringComparison.Ordinal))
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.DeviceMismatch);

        if (!string.Equals(token.RequestId, expectedRequestId, StringComparison.Ordinal))
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.RequestIdMismatch);

        if (token.ExpiresAtUtc <= _timeProvider.GetUtcNow())
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.Expired);

        // Consumed here (not after the hash check) so a single token — valid or not — can only
        // ever be presented for execution once, closing off repeated tamper attempts against it.
        var nonceWasFresh = await _nonceStore.TryConsumeAsync(token.Nonce, cancellationToken);
        if (!nonceWasFresh)
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.NonceReused);

        if (!string.Equals(token.Sha256Hex, currentFileSha256Hex, StringComparison.OrdinalIgnoreCase))
            return ApprovalValidationOutcome.Invalid(ApprovalRejectionReason.HashMismatch);

        return ApprovalValidationOutcome.Valid();
    }
}
