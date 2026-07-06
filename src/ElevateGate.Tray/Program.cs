using ElevateGate.Tray.Ipc;
using ElevateGate.Tray.UI;

namespace ElevateGate.Tray;

internal static class Program
{
    // Named so a second launch from the Explorer context menu can detect the tray is already
    // running rather than spawning a duplicate icon.
    private const string SingleInstanceMutexName = "Local\\ElevateGate.Tray.SingleInstance";

    [STAThread]
    private static void Main(string[] args)
    {
        using var singleInstanceMutex = new Mutex(initiallyOwned: true, SingleInstanceMutexName, out var createdNew);

        // The Explorer verb passes the selected file as the sole argument. Anything beyond
        // args[0] is ignored — this process never accepts flags, commands, or extra parameters.
        var initialFilePath = args.Length > 0 ? args[0] : null;

        if (!createdNew)
        {
            // A tray icon is already running for this user; hand it the file path to open a
            // request form for, rather than silently doing nothing.
            ActivationChannel.TrySendToRunningInstance(initialFilePath);
            return;
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new TrayApplicationContext(initialFilePath));
    }
}
