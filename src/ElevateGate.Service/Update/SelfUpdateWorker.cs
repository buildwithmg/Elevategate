using ElevateGate.Service.Options;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Update;

/// <summary>
/// The automatic, unattended half of updating: on a timer (AutoUpdateCheckIntervalHours), asks
/// <see cref="UpdateCoordinator"/> to check GitHub and apply anything newer. Gated on
/// AutoUpdateEnabled - the coordinator itself isn't, so a manual "update now" from the dashboard
/// (see Telemetry.TelemetryWorker) still works even with this timer disabled.
/// </summary>
public sealed class SelfUpdateWorker : BackgroundService
{
    // Gives the rest of the host (enrollment, the approval-polling loop) a clear run at startup
    // before this worker's first check competes for network/CPU.
    private static readonly TimeSpan InitialDelay = TimeSpan.FromMinutes(2);

    private readonly UpdateCoordinator _coordinator;
    private readonly ElevateGateServiceOptions _options;
    private readonly ILogger<SelfUpdateWorker> _logger;

    public SelfUpdateWorker(
        UpdateCoordinator coordinator,
        IOptions<ElevateGateServiceOptions> options,
        ILogger<SelfUpdateWorker> logger)
    {
        _coordinator = coordinator;
        _options = options.Value;
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
            await _coordinator.CheckAndApplyAsync(stoppingToken);
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }
}
