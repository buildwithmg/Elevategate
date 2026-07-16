namespace ElevateGate.Core.Update;

/// <summary>
/// Shared constants for the same-user, unauthenticated named pipe a second Tray launch (or, since
/// auto-update was added, the Service after installing a new version) uses to signal an
/// already-running Tray instance. Lives in Core - which both ElevateGate.Service and
/// ElevateGate.Tray already reference - purely so the Service can send on this pipe without a
/// project reference on Tray. See ElevateGate.Tray.Ipc.ActivationChannel for the actual pipe
/// server/listener.
/// </summary>
public static class TrayActivationProtocol
{
    public const string PipeName = "ElevateGate.Tray.Activation";

    /// <summary>
    /// Sent in place of a file path to mean "a new version was just installed on disk - relaunch
    /// yourself from it," not "open a request form for this file." Contains a colon in a
    /// non-drive-letter position, which is never valid inside a Windows file path, so it can
    /// never collide with a real activation request.
    /// </summary>
    public const string RestartForUpdateSentinel = "ELEVATEGATE:RESTART_FOR_UPDATE";
}
