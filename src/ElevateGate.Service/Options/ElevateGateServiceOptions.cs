namespace ElevateGate.Service.Options;

public sealed class ElevateGateServiceOptions
{
    public const string SectionName = "ElevateGate";

    /// <summary>Base URL of the backend API, e.g. https://elevategate.keystoneuae.com/.</summary>
    public string BackendBaseUrl { get; set; } = string.Empty;

    /// <summary>Base64-encoded Ed25519 public key, pinned at deployment time — never fetched at runtime.</summary>
    public string ServerPublicKeyBase64 { get; set; } = string.Empty;

    /// <summary>
    /// Pre-shared secret sent as the X-Enrollment-Key header on every enrollment call, gating the
    /// backend's otherwise-unauthenticated self-enrollment endpoint. Not part of any model the
    /// backend contract defines (EnrollmentRequest has no such field) - it's attached as a default
    /// header on the shared HttpClient in Program.cs, entirely outside of HttpApprovalApiClient's
    /// own wire-contract logic. Empty means no header is sent (only appropriate against a backend
    /// that doesn't require one).
    /// </summary>
    public string EnrollmentKey { get; set; } = string.Empty;

    /// <summary>How often to poll the backend for outstanding decisions.</summary>
    public int PollingIntervalSeconds { get; set; } = 15;

    /// <summary>Directory for local state: device credential, nonce ledger, audit log, logs. Defaults to ProgramData.</summary>
    public string DataDirectory { get; set; } = @"C:\ProgramData\ElevateGate";

    public string PipeName { get; set; } = "ElevateGate.Agent";

    /// <summary>Absolute path the connecting pipe client's process image must match exactly.</summary>
    public string ExpectedTrayExecutablePath { get; set; } = @"C:\Program Files\ElevateGate\ElevateGate.Tray.exe";

    /// <summary>How long an approval request may remain pending before the service gives up on it locally.</summary>
    public int RequestTimeToLiveMinutes { get; set; } = 30;

    /// <summary>Whether to periodically check GitHub Releases for a newer build and install it automatically.</summary>
    public bool AutoUpdateEnabled { get; set; } = true;

    /// <summary>How often to check for a newer release.</summary>
    public int AutoUpdateCheckIntervalHours { get; set; } = 6;

    /// <summary>
    /// GitHub "owner/repo" to check for releases - see ElevateGate.Core.Update.GitHubUpdateChecker.
    /// </summary>
    public string UpdateRepository { get; set; } = "buildwithmg/Elevategate";

    /// <summary>
    /// The name this process is registered under with the Service Control Manager (what
    /// `New-Service -Name` / `sc create` used at install time) - needed so the self-updater can
    /// restart the *service*, not just replace its files. Must match whatever the install script
    /// was actually run with if `-ServiceName` was ever overridden from its default.
    /// </summary>
    public string ServiceName { get; set; } = "ElevateGateAgent";
}
