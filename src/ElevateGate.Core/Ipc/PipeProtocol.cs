namespace ElevateGate.Core.Ipc;

/// <summary>
/// The complete, closed set of messages the service's named pipe will ever accept. There is
/// deliberately no message type carrying a command, script, or argument list — only a candidate
/// file path and a human-supplied reason, both of which the service treats as untrusted and
/// re-derives/re-validates itself.
/// </summary>
public enum PipeMessageType
{
    SubmitRequest,
    GetStatus,
}

public sealed record PipeRequestMessage(PipeMessageType Type, string? FilePath, string? Reason, string? RequestId);

public sealed record PipeResponseMessage(bool Success, string? RequestId, string? Status, string? ErrorMessage);
