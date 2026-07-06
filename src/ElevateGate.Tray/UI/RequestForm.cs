using ElevateGate.Core.Ipc;
using ElevateGate.Tray.Ipc;

namespace ElevateGate.Tray.UI;

/// <summary>
/// Lets the user pick (or confirm) an installer and state a reason, submits it to the service,
/// and polls for the outcome. This form never talks to the backend directly and never decides
/// anything itself — it only relays the user's request and displays whatever status the service
/// reports back.
/// </summary>
public sealed class RequestForm : Form
{
    private readonly PipeClient _pipeClient;
    private readonly NotifyIcon _notifyIcon;
    private readonly bool _pathWasPrefilled;

    private readonly TextBox _filePathTextBox = new() { ReadOnly = true, Width = 360 };
    private readonly Button _browseButton = new() { Text = "Browse..." };
    private readonly TextBox _reasonTextBox = new() { Multiline = true, Height = 80, Width = 440 };
    private readonly Button _submitButton = new() { Text = "Request Approval" };
    private readonly Label _statusLabel = new() { AutoSize = true, Text = "" };
    private readonly System.Windows.Forms.Timer _pollTimer = new() { Interval = 3000 };

    private string? _requestId;

    public RequestForm(PipeClient pipeClient, string? prefilledFilePath, NotifyIcon notifyIcon)
    {
        _pipeClient = pipeClient;
        _notifyIcon = notifyIcon;
        _pathWasPrefilled = !string.IsNullOrWhiteSpace(prefilledFilePath);

        Text = "ElevateGate - Request IT Approval";
        FormBorderStyle = FormBorderStyle.FixedDialog;
        MaximizeBox = false;
        MinimizeBox = false;
        StartPosition = FormStartPosition.CenterScreen;
        AutoSize = true;
        AutoSizeMode = AutoSizeMode.GrowAndShrink;
        Padding = new Padding(12);

        if (_pathWasPrefilled)
        {
            _filePathTextBox.Text = prefilledFilePath;
            _browseButton.Enabled = false;
        }

        _browseButton.Click += OnBrowseClicked;
        _submitButton.Click += OnSubmitClicked;
        _pollTimer.Tick += OnPollTick;

        BuildLayout();
    }

    private void BuildLayout()
    {
        var layout = new TableLayoutPanel
        {
            ColumnCount = 2,
            AutoSize = true,
            AutoSizeMode = AutoSizeMode.GrowAndShrink,
        };

        layout.Controls.Add(new Label { Text = "File:", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0);
        var filePanel = new FlowLayoutPanel { AutoSize = true, FlowDirection = FlowDirection.LeftToRight };
        filePanel.Controls.Add(_filePathTextBox);
        filePanel.Controls.Add(_browseButton);
        layout.Controls.Add(filePanel, 1, 0);

        layout.Controls.Add(new Label { Text = "Reason:", AutoSize = true, Anchor = AnchorStyles.Top | AnchorStyles.Left }, 0, 1);
        layout.Controls.Add(_reasonTextBox, 1, 1);

        layout.Controls.Add(_submitButton, 1, 2);
        layout.Controls.Add(_statusLabel, 1, 3);

        Controls.Add(layout);
    }

    private void OnBrowseClicked(object? sender, EventArgs e)
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Select an installer",
            Filter = "Installers (*.exe;*.msi)|*.exe;*.msi",
            CheckFileExists = true,
            Multiselect = false,
        };

        if (dialog.ShowDialog(this) == DialogResult.OK)
            _filePathTextBox.Text = dialog.FileName;
    }

    private async void OnSubmitClicked(object? sender, EventArgs e)
    {
        var filePath = _filePathTextBox.Text.Trim();
        var reason = _reasonTextBox.Text.Trim();

        if (string.IsNullOrWhiteSpace(filePath))
        {
            SetStatus("Please choose a file first.");
            return;
        }

        if (reason.Length < 5)
        {
            SetStatus("Please enter a reason (at least 5 characters).");
            return;
        }

        SetInputsEnabled(false);
        SetStatus("Submitting request...");

        try
        {
            var response = await _pipeClient.SubmitRequestAsync(filePath, reason);
            if (!response.Success)
            {
                SetStatus($"Rejected: {response.ErrorMessage}");
                SetInputsEnabled(true);
                return;
            }

            _requestId = response.RequestId;
            SetStatus($"Status: {response.Status}");
            _pollTimer.Start();
        }
        catch (Exception ex)
        {
            SetStatus($"Failed to reach ElevateGate service: {ex.Message}");
            SetInputsEnabled(true);
        }
    }

    private async void OnPollTick(object? sender, EventArgs e)
    {
        if (_requestId is null)
            return;

        try
        {
            var response = await _pipeClient.GetStatusAsync(_requestId);
            if (!response.Success)
            {
                SetStatus($"Status check failed: {response.ErrorMessage}");
                return;
            }

            SetStatus($"Status: {response.Status}");

            if (IsTerminalStatus(response.Status))
            {
                _pollTimer.Stop();
                NotifyOutcome(response.Status);
                SetInputsEnabled(true);
            }
        }
        catch (Exception ex)
        {
            SetStatus($"Status check failed: {ex.Message}");
        }
    }

    private void NotifyOutcome(string? status)
    {
        var (icon, message) = status switch
        {
            nameof(Core.Models.RequestStatus.Approved) => (ToolTipIcon.Info, "Your request was approved and is running."),
            nameof(Core.Models.RequestStatus.Denied) => (ToolTipIcon.Warning, "Your request was denied."),
            nameof(Core.Models.RequestStatus.Expired) => (ToolTipIcon.Warning, "Your request expired before it was decided."),
            _ => (ToolTipIcon.Error, "Your request could not be completed."),
        };

        _notifyIcon.BalloonTipIcon = icon;
        _notifyIcon.BalloonTipTitle = "ElevateGate";
        _notifyIcon.BalloonTipText = message;
        _notifyIcon.ShowBalloonTip(5000);
    }

    private static bool IsTerminalStatus(string? status) =>
        status is nameof(Core.Models.RequestStatus.Approved)
            or nameof(Core.Models.RequestStatus.Denied)
            or nameof(Core.Models.RequestStatus.Expired)
            or nameof(Core.Models.RequestStatus.Failed);

    private void SetStatus(string text) => _statusLabel.Text = text;

    private void SetInputsEnabled(bool enabled)
    {
        _browseButton.Enabled = enabled && !_pathWasPrefilled;
        _reasonTextBox.Enabled = enabled;
        _submitButton.Enabled = enabled;
    }
}
