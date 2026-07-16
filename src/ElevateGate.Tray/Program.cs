using ElevateGate.Tray.Ipc;
using ElevateGate.Tray.UI;

namespace ElevateGate.Tray;

internal static class Program
{
    // Named so a second launch from the Explorer context menu can detect the tray is already
    // running rather than spawning a duplicate icon.
    private const string SingleInstanceMutexName = "Local\\ElevateGate.Tray.SingleInstance";

    /// <summary>
    /// Passed by the *already-running*, unelevated tray instance to a new copy of itself launched
    /// with Verb="runas" (see TrayApplicationContext.TryElevatedExit). This process's only job is
    /// to exist - successfully launching and running it at all proves the user approved the UAC
    /// prompt, which is what the waiting instance actually checks (via exit code / lack of a
    /// thrown Win32Exception), not anything this branch does itself. Never creates the
    /// single-instance mutex, never shows any UI.
    /// </summary>
    internal const string ConfirmExitArg = "--confirm-exit";

    [STAThread]
    private static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == ConfirmExitArg)
            return 0;

        using var singleInstanceMutex = new Mutex(initiallyOwned: true, SingleInstanceMutexName, out var createdNew);

        // The Explorer verb passes the selected file as the sole argument. Anything beyond
        // args[0] is ignored — this process never accepts flags, commands, or extra parameters.
        var initialFilePath = args.Length > 0 ? args[0] : null;

        if (!createdNew)
        {
            // A tray icon is already running for this user; hand it the file path to open a
            // request form for, rather than silently doing nothing.
            ActivationChannel.TrySendToRunningInstance(initialFilePath);
            return 0;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new TrayApplicationContext(initialFilePath));
        return 0;
    }
}
