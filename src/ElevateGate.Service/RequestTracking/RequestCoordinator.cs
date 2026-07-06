using System.Diagnostics;
using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Hashing;
using ElevateGate.Core.Ipc;
using ElevateGate.Core.Models;
using ElevateGate.Core.Validation;
using ElevateGate.Service.Enrollment;
using Microsoft.Extensions.Logging;

namespace ElevateGate.Service.RequestTracking;

/// <summary>
/// Handles a SubmitRequest message from the tray. The tray-supplied path is treated purely as a
/// hint: every field sent to the backend (path, hash, size, version, signature) is re-derived
/// here from the file on disk, never taken from the tray's message.
/// </summary>
public sealed class RequestCoordinator
{
    private static readonly HashSet<string> AllowedExtensions = new(StringComparer.OrdinalIgnoreCase) { ".exe", ".msi" };

    private readonly PathValidator _pathValidator;
    private readonly ISignatureInspector _signatureInspector;
    private readonly IApprovalApiClient _apiClient;
    private readonly IDeviceCredentialStore _credentialStore;
    private readonly RequestStateStore _stateStore;
    private readonly IAuditLog _auditLog;
    private readonly ILogger<RequestCoordinator> _logger;

    public RequestCoordinator(
        PathValidator pathValidator,
        ISignatureInspector signatureInspector,
        IApprovalApiClient apiClient,
        IDeviceCredentialStore credentialStore,
        RequestStateStore stateStore,
        IAuditLog auditLog,
        ILogger<RequestCoordinator> logger)
    {
        _pathValidator = pathValidator;
        _signatureInspector = signatureInspector;
        _apiClient = apiClient;
        _credentialStore = credentialStore;
        _stateStore = stateStore;
        _auditLog = auditLog;
        _logger = logger;
    }

    public async Task<PipeResponseMessage> SubmitAsync(string? rawFilePath, string? reason, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(rawFilePath))
            return Failed(null, "A file path is required.");

        if (string.IsNullOrWhiteSpace(reason))
            return Failed(null, "A reason is required.");

        var pathOutcome = _pathValidator.Validate(rawFilePath);
        if (!pathOutcome.IsValid)
        {
            await _auditLog.RecordAsync(new AuditEvent(
                DateTimeOffset.UtcNow, AuditEventType.ValidationRejected, null, null, null,
                $"Path rejected at submission: {pathOutcome.Reason}"), cancellationToken);
            return Failed(null, $"Path rejected: {pathOutcome.Reason}");
        }

        var canonicalPath = pathOutcome.CanonicalPath!;
        var extension = Path.GetExtension(canonicalPath);
        if (!AllowedExtensions.Contains(extension))
            return Failed(null, "Only .exe and .msi files may be requested.");

        if (!File.Exists(canonicalPath))
            return Failed(null, "File not found.");

        var credential = await _credentialStore.GetOrCreateAsync(cancellationToken);
        var fileInfo = new FileInfo(canonicalPath);
        var sha256Hex = await Sha256FileHasher.ComputeHexAsync(canonicalPath, cancellationToken);
        var fileVersion = TryGetFileVersion(canonicalPath);
        var signature = _signatureInspector.Inspect(canonicalPath);
        var metadata = new FileMetadata(fileInfo.Name, canonicalPath, fileInfo.Length, fileVersion, sha256Hex);

        var requestId = Guid.NewGuid().ToString("N");
        var request = new ApprovalRequest(requestId, credential.DeviceId, metadata, signature, reason, DateTimeOffset.UtcNow);

        _stateStore.Add(requestId, new TrackedRequest(canonicalPath, reason, request.RequestedAtUtc, RequestStatus.Pending));

        try
        {
            await _apiClient.SubmitRequestAsync(credential.BearerToken, request, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to submit approval request {RequestId} to backend.", requestId);
            _stateStore.UpdateStatus(requestId, RequestStatus.Failed);
            return Failed(requestId, "Could not reach the approval backend.");
        }

        await _auditLog.RecordAsync(new AuditEvent(
            DateTimeOffset.UtcNow, AuditEventType.RequestSubmitted, requestId, credential.DeviceId, null,
            $"Submitted {metadata.FileName}."), cancellationToken);

        return new PipeResponseMessage(true, requestId, RequestStatus.Pending.ToString(), null);
    }

    public PipeResponseMessage GetStatus(string? requestId)
    {
        if (string.IsNullOrWhiteSpace(requestId))
            return Failed(null, "A request id is required.");

        var tracked = _stateStore.Get(requestId);
        return tracked is null
            ? Failed(requestId, "Unknown request id.")
            : new PipeResponseMessage(true, requestId, tracked.Status.ToString(), null);
    }

    private static string? TryGetFileVersion(string canonicalPath)
    {
        try
        {
            return FileVersionInfo.GetVersionInfo(canonicalPath).FileVersion;
        }
        catch
        {
            return null;
        }
    }

    private static PipeResponseMessage Failed(string? requestId, string errorMessage) =>
        new(false, requestId, RequestStatus.Failed.ToString(), errorMessage);
}
