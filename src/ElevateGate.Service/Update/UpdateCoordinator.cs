using ElevateGate.Core.Update;
using ElevateGate.Service.Options;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Update;

/// <summary>
/// Checks GitHub Releases for a newer build and, if found, downloads and applies it. Shared by
/// two independent triggers: <see cref="SelfUpdateWorker"/>'s own timer (gated on
/// AutoUpdateEnabled), and an admin's "update now" from the dashboard, relayed via a heartbeat
/// response's `updateRequested: true` (see Telemetry.TelemetryWorker) - deliberately NOT gated on
/// AutoUpdateEnabled, since a manual request should still work even with the automatic timer
/// turned off (that's the whole point of offering "update now" as a fallback).
///
/// A broken or unreachable update channel must never disrupt the actual job (polling for and
/// executing approvals) - every failure here is caught and logged, never thrown.
/// </summary>
public sealed class UpdateCoordinator
{
    private readonly GitHubUpdateChecker _updateChecker;
    private readonly SelfUpdateApplier _applier;
    private readonly ElevateGateServiceOptions _options;
    private readonly IHostApplicationLifetime _lifetime;
    private readonly ILogger<UpdateCoordinator> _logger;
    // Guards against SelfUpdateWorker's timer and a heartbeat-triggered check overlapping and
    // both trying to download/apply/restart at once.
    private readonly SemaphoreSlim _gate = new(1, 1);

    public UpdateCoordinator(
        GitHubUpdateChecker updateChecker,
        SelfUpdateApplier applier,
        IOptions<ElevateGateServiceOptions> options,
        IHostApplicationLifetime lifetime,
        ILogger<UpdateCoordinator> logger)
    {
        _updateChecker = updateChecker;
        _applier = applier;
        _options = options.Value;
        _lifetime = lifetime;
        _logger = logger;
    }

    public async Task CheckAndApplyAsync(CancellationToken cancellationToken)
    {
        if (!await _gate.WaitAsync(0, cancellationToken))
        {
            _logger.LogInformation("An update check is already in progress; skipping this trigger.");
            return;
        }

        try
        {
            var currentVersion = typeof(UpdateCoordinator).Assembly.GetName().Version ?? new Version(0, 0, 0, 0);
            var release = await _updateChecker.GetLatestReleaseAsync(_options.UpdateRepository, cancellationToken);
            if (release is null)
                return;

            if (!GitHubUpdateChecker.IsNewer(currentVersion, release.TagName))
                return;

            _logger.LogInformation(
                "Update {Tag} available (currently running {Current}); downloading and applying.",
                release.TagName, currentVersion);

            await _applier.ApplyAsync(release, cancellationToken);

            // The applier already handed off an external restart of this service to a detached
            // helper process; stop cleanly now rather than keep running the old build until that
            // restart lands.
            _lifetime.StopApplication();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Update check/apply failed; a later trigger will retry.");
        }
        finally
        {
            _gate.Release();
        }
    }
}
