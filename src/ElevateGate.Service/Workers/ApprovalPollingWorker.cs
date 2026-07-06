using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Models;
using ElevateGate.Service.Enrollment;
using ElevateGate.Service.Execution;
using ElevateGate.Service.Options;
using ElevateGate.Service.RequestTracking;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Workers;

/// <summary>
/// Periodically asks the backend for decisions on outstanding requests. When a decision is
/// "Approved," this is the only code path that hands a token to <see cref="ExecutionEngine"/> —
/// and even then, the engine independently re-validates everything before running anything.
/// </summary>
public sealed class ApprovalPollingWorker : BackgroundService
{
    private readonly IApprovalApiClient _apiClient;
    private readonly IDeviceCredentialStore _credentialStore;
    private readonly RequestStateStore _stateStore;
    private readonly ExecutionEngine _executionEngine;
    private readonly IAuditLog _auditLog;
    private readonly ElevateGateServiceOptions _options;
    private readonly ILogger<ApprovalPollingWorker> _logger;

    public ApprovalPollingWorker(
        IApprovalApiClient apiClient,
        IDeviceCredentialStore credentialStore,
        RequestStateStore stateStore,
        ExecutionEngine executionEngine,
        IAuditLog auditLog,
        IOptions<ElevateGateServiceOptions> options,
        ILogger<ApprovalPollingWorker> logger)
    {
        _apiClient = apiClient;
        _credentialStore = credentialStore;
        _stateStore = stateStore;
        _executionEngine = executionEngine;
        _auditLog = auditLog;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var credential = await _credentialStore.GetOrCreateAsync(stoppingToken);
        var sinceUtc = DateTimeOffset.UtcNow;

        using var timer = new PeriodicTimer(TimeSpan.FromSeconds(Math.Max(1, _options.PollingIntervalSeconds)));
        do
        {
            try
            {
                await PollOnceAsync(credential, sinceUtc, stoppingToken);
                sinceUtc = DateTimeOffset.UtcNow;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Approval polling cycle failed.");
            }
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }

    private async Task PollOnceAsync(DeviceCredential credential, DateTimeOffset sinceUtc, CancellationToken cancellationToken)
    {
        var decisions = await _apiClient.PollDecisionsAsync(credential.BearerToken, credential.DeviceId, sinceUtc, cancellationToken);
        foreach (var decision in decisions)
        {
            await HandleDecisionAsync(credential, decision, cancellationToken);
        }
    }

    private async Task HandleDecisionAsync(DeviceCredential credential, ApprovalDecision decision, CancellationToken cancellationToken)
    {
        var tracked = _stateStore.Get(decision.RequestId);
        if (tracked is null)
        {
            _logger.LogWarning("Received decision for unrecognized request {RequestId}; ignoring.", decision.RequestId);
            return;
        }

        await _auditLog.RecordAsync(new AuditEvent(
            DateTimeOffset.UtcNow, AuditEventType.DecisionReceived, decision.RequestId, credential.DeviceId,
            decision.Token?.Nonce, decision.Status.ToString()), cancellationToken);

        switch (decision.Status)
        {
            case RequestStatus.Denied:
            case RequestStatus.Expired:
                _stateStore.UpdateStatus(decision.RequestId, decision.Status);
                break;

            case RequestStatus.Approved:
                await HandleApprovedAsync(credential, decision, tracked, cancellationToken);
                break;

            default:
                _logger.LogWarning(
                    "Ignoring unexpected decision status {Status} for request {RequestId}.",
                    decision.Status, decision.RequestId);
                break;
        }
    }

    private async Task HandleApprovedAsync(
        DeviceCredential credential, ApprovalDecision decision, TrackedRequest tracked, CancellationToken cancellationToken)
    {
        if (decision.Token is null)
        {
            _logger.LogError(
                "Backend reported Approved for request {RequestId} without a token; treating as failed.", decision.RequestId);
            _stateStore.UpdateStatus(decision.RequestId, RequestStatus.Failed);
            return;
        }

        var outcome = await _executionEngine.ExecuteAsync(
            decision.Token, decision.RequestId, tracked.CanonicalPath, credential.DeviceId, cancellationToken);
        _stateStore.UpdateStatus(decision.RequestId, outcome.Success ? RequestStatus.Approved : RequestStatus.Failed);

        await _auditLog.RecordAsync(new AuditEvent(
            DateTimeOffset.UtcNow,
            outcome.Success ? AuditEventType.ExecutionCompleted : AuditEventType.ExecutionFailed,
            decision.RequestId, credential.DeviceId, decision.Token.Nonce,
            outcome.Success ? "Execution completed." : $"Execution failed: {outcome.FailureReason}"), cancellationToken);
    }
}
