using ElevateGate.Core.Abstractions;
using ElevateGate.Service.Enrollment;
using ElevateGate.Service.Options;
using ElevateGate.Service.Update;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Telemetry;

/// <summary>
/// Periodically reports disk/RAM/agent-version telemetry to the backend (POST /api/v1/heartbeat)
/// and, if the response says an admin asked for an update from the dashboard
/// (`updateRequested: true`), immediately asks <see cref="UpdateCoordinator"/> to check for and
/// apply one rather than waiting for SelfUpdateWorker's own timer - this is the fallback path for
/// "auto-update didn't already handle it."
/// </summary>
public sealed class TelemetryWorker : BackgroundService
{
    private static readonly TimeSpan InitialDelay = TimeSpan.FromSeconds(30);

    private readonly IApprovalApiClient _apiClient;
    private readonly IDeviceCredentialStore _credentialStore;
    private readonly SystemTelemetryCollector _collector;
    private readonly UpdateCoordinator _updateCoordinator;
    private readonly ElevateGateServiceOptions _options;
    private readonly ILogger<TelemetryWorker> _logger;

    public TelemetryWorker(
        IApprovalApiClient apiClient,
        IDeviceCredentialStore credentialStore,
        SystemTelemetryCollector collector,
        UpdateCoordinator updateCoordinator,
        IOptions<ElevateGateServiceOptions> options,
        ILogger<TelemetryWorker> logger)
    {
        _apiClient = apiClient;
        _credentialStore = credentialStore;
        _collector = collector;
        _updateCoordinator = updateCoordinator;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        try
        {
            await Task.Delay(InitialDelay, stoppingToken);
        }
        catch (OperationCanceledException)
        {
            return;
        }

        var interval = TimeSpan.FromMinutes(Math.Max(1, _options.TelemetryIntervalMinutes));
        using var timer = new PeriodicTimer(interval);

        do
        {
            await SendHeartbeatOnceAsync(stoppingToken);
        } while (await timer.WaitForNextTickAsync(stoppingToken));
    }

    private async Task SendHeartbeatOnceAsync(CancellationToken cancellationToken)
    {
        try
        {
            var credential = await _credentialStore.GetOrCreateAsync(cancellationToken);
            var request = _collector.Collect();
            var result = await _apiClient.SendHeartbeatAsync(credential.BearerToken, request, cancellationToken);

            if (result.UpdateRequested)
            {
                _logger.LogInformation("An update was requested from the dashboard; checking now.");
                await _updateCoordinator.CheckAndApplyAsync(cancellationToken);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Heartbeat failed; will retry on the next interval.");
        }
    }
}
