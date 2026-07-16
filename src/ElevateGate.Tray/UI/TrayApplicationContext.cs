using System.ComponentModel;
using System.Diagnostics;
using ElevateGate.Core.Update;
using ElevateGate.Tray.Ipc;

namespace ElevateGate.Tray.UI;

/// <summary>Owns the tray icon's lifetime. The process has no main window — it lives entirely as a tray presence until the user chooses Exit.</summary>
public sealed class TrayApplicationContext : ApplicationContext
{
    private readonly NotifyIcon _notifyIcon;
    private readonly PipeClient _pipeClient = new();
    private readonly Control _uiThreadMarshal = new();
    private readonly CancellationTokenSource _activationListenerCts = new();

    public TrayApplicationContext(string? initialFilePath)
    {
        // Never shown; exists solely to give ActivationChannel's background listener a handle
        // to marshal back onto the UI thread with Invoke.
        _uiThreadMarshal.CreateControl();

        var menu = new ContextMenuStrip();
        menu.Items.Add("Request IT Approval...", null, (_, _) => OpenRequestForm(null));
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Exit", null, (_, _) => TryElevatedExit());

        _notifyIcon = new NotifyIcon
        {
            Icon = SystemIcons.Shield,
            Text = "ElevateGate Agent",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _notifyIcon.DoubleClick += (_, _) => OpenRequestForm(null);

        ActivationChannel.StartListening(
            path => _uiThreadMarshal.Invoke(() => HandleActivation(path)),
            _activationListenerCts.Token);

        if (!string.IsNullOrWhiteSpace(initialFilePath))
            OpenRequestForm(initialFilePath);
    }

    private void HandleActivation(string? pathOrSentinel)
    {
        if (pathOrSentinel == TrayActivationProtocol.RestartForUpdateSentinel)
        {
            RestartForUpdate();
            return;
        }

        OpenRequestForm(pathOrSentinel);
    }

    private void OpenRequestForm(string? prefilledPath)
    {
        using var form = new RequestForm(_pipeClient, prefilledPath, _notifyIcon);
        form.ShowDialog();
    }

    /// <summary>
    /// Sent by the Service (already elevated) after it swaps ElevateGate.Tray.exe on disk for a
    /// newer version. Unlike the user-initiated "Exit," this needs no UAC prompt - it never
    /// writes anything, just launches the (already-replaced-by-the-Service) exe fresh as this
    /// same unelevated user and lets this instance go. There's a brief gap with no tray icon
    /// while the new process starts, not a gap in actual protection - the Service keeps enforcing
    /// approvals throughout regardless of whether the tray is running at all.
    /// </summary>
    private void RestartForUpdate()
    {
        var exePath = Environment.ProcessPath;
        if (string.IsNullOrEmpty(exePath) || !File.Exists(exePath))
            return;

        try
        {
            Process.Start(new ProcessStartInfo { FileName = exePath, UseShellExecute = true });
        }
        catch (Exception)
        {
            // If relaunching the new build fails for any reason, staying on the (still-running,
            // still-functional) old build is safer than exiting into nothing.
            return;
        }

        ExitThread();
    }

    /// <summary>
    /// The tray deliberately runs unelevated - it's a thin UI in front of the elevated Service,
    /// never a trust boundary itself - so it can't silence its own UAC prompt in-process. Instead,
    /// it launches a copy of itself elevated (Verb="runas") purely to make Windows show the
    /// consent prompt; that copy does nothing but return 0 (see Program.ConfirmExitArg) and exit.
    /// Only if that succeeds - the user actually clicked "Yes" - does this instance exit itself.
    /// Declining the prompt (or closing it) throws Win32Exception 1223 and the tray just stays up.
    /// </summary>
    private void TryElevatedExit()
    {
        var exePath = Environment.ProcessPath;
        if (string.IsNullOrEmpty(exePath))
            return;

        try
        {
            using var confirmProcess = Process.Start(new ProcessStartInfo
            {
                FileName = exePath,
                Arguments = Program.ConfirmExitArg,
                UseShellExecute = true,
                Verb = "runas",
            });
            confirmProcess?.WaitForExit();

            if (confirmProcess is { ExitCode: 0 })
                ExitThread();
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            // ERROR_CANCELLED: the user declined the elevation prompt. Exiting requires
            // administrator approval, so nothing happens - the tray keeps running.
            _notifyIcon.ShowBalloonTip(
                3000, "ElevateGate Agent", "Exiting requires administrator approval.", ToolTipIcon.Info);
        }
    }

    protected override void ExitThreadCore()
    {
        _activationListenerCts.Cancel();
        _notifyIcon.Visible = false;
        _notifyIcon.Dispose();
        _uiThreadMarshal.Dispose();
        base.ExitThreadCore();
    }
}
