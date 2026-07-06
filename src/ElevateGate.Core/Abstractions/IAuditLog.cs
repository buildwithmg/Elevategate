namespace ElevateGate.Core.Abstractions;

public enum AuditEventType
{
    DeviceEnrolled,
    RequestSubmitted,
    DecisionReceived,
    ValidationRejected,
    ExecutionStarted,
    ExecutionCompleted,
    ExecutionFailed,
}

public sealed record AuditEvent(
    DateTimeOffset TimestampUtc,
    AuditEventType EventType,
    string? RequestId,
    string? DeviceId,
    string? Nonce,
    string Message);

/// <summary>Append-only local audit trail. Never deleted or mutated by the agent itself.</summary>
public interface IAuditLog
{
    Task RecordAsync(AuditEvent auditEvent, CancellationToken cancellationToken = default);
}
