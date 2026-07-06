using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using ElevateGate.Core.Ipc;

namespace ElevateGate.Tray.Ipc;

/// <summary>
/// Talks to ElevateGate.Service over its named pipe. Sends exactly one of the two closed
/// message types and nothing else — this client has no way to express an arbitrary command
/// even if it wanted to, because <see cref="PipeRequestMessage"/> doesn't have a field for one.
/// </summary>
public sealed class PipeClient
{
    private const string PipeName = "ElevateGate.Agent";
    private static readonly TimeSpan ConnectTimeout = TimeSpan.FromSeconds(5);

    public Task<PipeResponseMessage> SubmitRequestAsync(string filePath, string reason, CancellationToken cancellationToken = default) =>
        SendAsync(new PipeRequestMessage(PipeMessageType.SubmitRequest, filePath, reason, null), cancellationToken);

    public Task<PipeResponseMessage> GetStatusAsync(string requestId, CancellationToken cancellationToken = default) =>
        SendAsync(new PipeRequestMessage(PipeMessageType.GetStatus, null, null, requestId), cancellationToken);

    private static async Task<PipeResponseMessage> SendAsync(PipeRequestMessage message, CancellationToken cancellationToken)
    {
        using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut, PipeOptions.Asynchronous);
        await pipe.ConnectAsync((int)ConnectTimeout.TotalMilliseconds, cancellationToken);

        using var writer = new StreamWriter(pipe, Encoding.UTF8, leaveOpen: true) { AutoFlush = true };
        using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);

        await writer.WriteLineAsync(JsonSerializer.Serialize(message));

        var line = await reader.ReadLineAsync(cancellationToken)
            ?? throw new IOException("ElevateGate service closed the connection without responding.");

        return JsonSerializer.Deserialize<PipeResponseMessage>(line)
            ?? throw new IOException("ElevateGate service returned a malformed response.");
    }
}
