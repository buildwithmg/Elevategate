namespace ElevateGate.Service.Execution;

public sealed record ExecutionOutcome(bool Success, string? FailureReason)
{
    public static ExecutionOutcome Ok() => new(true, null);

    public static ExecutionOutcome Failed(string reason) => new(false, reason);
}
