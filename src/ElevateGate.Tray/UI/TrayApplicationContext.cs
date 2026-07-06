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
        menu.Items.Add("Exit", null, (_, _) => ExitThread());

        _notifyIcon = new NotifyIcon
        {
            Icon = SystemIcons.Shield,
            Text = "ElevateGate Agent",
            Visible = true,
            ContextMenuStrip = menu,
        };
        _notifyIcon.DoubleClick += (_, _) => OpenRequestForm(null);

        ActivationChannel.StartListening(
            path => _uiThreadMarshal.Invoke(() => OpenRequestForm(path)),
            _activationListenerCts.Token);

        if (!string.IsNullOrWhiteSpace(initialFilePath))
            OpenRequestForm(initialFilePath);
    }

    private void OpenRequestForm(string? prefilledPath)
    {
        using var form = new RequestForm(_pipeClient, prefilledPath, _notifyIcon);
        form.ShowDialog();
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
