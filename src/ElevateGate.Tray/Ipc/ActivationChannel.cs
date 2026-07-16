using System.IO.Pipes;
using ElevateGate.Core.Update;

namespace ElevateGate.Tray.Ipc;

/// <summary>
/// Lets a second launch of the tray (from the Explorer "Request IT Approval" verb, while the
/// tray is already running in the background) hand its file path to the already-running
/// instance instead of silently doing nothing. Purely a same-user UI convenience — carries no
/// security weight, since the service re-validates any path it's ever given regardless of which
/// tray instance forwarded it. Also used by the Service (see SelfUpdateApplier) to tell an
/// already-running tray to relaunch itself after an auto-update - see
/// TrayActivationProtocol.RestartForUpdateSentinel.
/// </summary>
public static class ActivationChannel
{
    private const string PipeName = TrayActivationProtocol.PipeName;

    public static bool TrySendToRunningInstance(string? filePath)
    {
        try
        {
            using var pipe = new NamedPipeClientStream(".", PipeName, PipeDirection.Out);
            pipe.Connect(2000);
            using var writer = new StreamWriter(pipe) { AutoFlush = true };
            writer.WriteLine(filePath ?? string.Empty);
            return true;
        }
        catch (Exception)
        {
            return false;
        }
    }

    public static void StartListening(Action<string?> onActivationRequested, CancellationToken cancellationToken)
    {
        _ = Task.Run(async () =>
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    using var pipe = new NamedPipeServerStream(
                        PipeName, PipeDirection.In, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
                    await pipe.WaitForConnectionAsync(cancellationToken);

                    using var reader = new StreamReader(pipe);
                    var line = await reader.ReadLineAsync(cancellationToken);
                    onActivationRequested(string.IsNullOrEmpty(line) ? null : line);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (IOException)
                {
                    // Transient pipe error; recreate the server instance and keep listening.
                }
            }
        }, cancellationToken);
    }
}
