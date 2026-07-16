using ElevateGate.Core.Update;
using ElevateGate.Service.Options;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Update;

/// <summary>
/// Periodically checks GitHub Releases for a newer build and, if found, downloads and installs
/// it via <see cref="SelfUpdateApplier"/>. A broken or unreachable update channel must never
/// disrupt the actual job (polling for and executing approvals) - every failure here is caught,
/// logged, and simply retried on the next interval.
/// </summary>
public sealed class SelfUpdateWorker : BackgroundService
{
    // Gives the rest of the host (enrollment, the approval-polling loop) a clear run at startup
    // before this worker's first check competes for network/CPU.
    private static readonly TimeSpan InitialDelay = TimeSpan.FromMinutes(2);

    private readonly GitHubUpdateChecker _updateChecker;
    private readonly SelfUpdateApplier _applier;
    private readonly ElevateGateServiceOptions _options;
    private readonly IHostApplicationLifetime _lifetime;
    private readonly ILogger<SelfUpdateWorker> _logger;

    public SelfUpdateWorker(
        GitHubUpdateChecker updateChecker,
        SelfUpdateApplier applier,
        IOptions<ElevateGateServiceOptions> options,
        IHostApplicationLifetime lifetime,
        ILogger<SelfUpdateWorker> logger)
    {
        _updateChecker = updateChecker;
        _applier = applier;
        _options = options.Value;
        _lifetime = lifetime;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_options.AutoUpdateEnabled)
        {
            _logger.LogInformation("Auto-update is disabled (ElevateGate:AutoUpdateEnabled=false).");
            return;
        }

        try
        {
            await Task.Delay(InitialDelay, stoppingToken);
        }
        catch (OperationCanceledException)
        {
            return;
        }

        var interval = TimeSpan.FromHours(Math.Max(1, _options.AutoUpdateCheckIntervalHours));
        using var timer = new PeriodicTimer(interval);

        do
        {
            await CheckOnceAsync(stoppingToken);
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }

    private async Task CheckOnceAsync(CancellationToken cancellationToken)
    {
        try
        {
            var currentVersion = typeof(SelfUpdateWorker).Assembly.GetName().Version ?? new Version(0, 0, 0, 0);
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
            _logger.LogError(ex, "Auto-update check failed; will retry on the next interval.");
        }
    }
}
