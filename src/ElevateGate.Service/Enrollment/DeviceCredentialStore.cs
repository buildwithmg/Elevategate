using System.Text;
using System.Text.Json;
using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Models;
using ElevateGate.Service.Options;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Enrollment;

/// <summary>
/// Generates a unique device id and enrolls with the backend on first run, then persists the
/// resulting bearer token DPAPI-encrypted on disk. The device id itself is not secret and is
/// stored in the clear alongside the encrypted token; only the token is protected.
/// Never stores or transmits an administrator password — enrollment issues a scoped bearer
/// token, nothing else.
/// </summary>
public sealed class DeviceCredentialStore : IDeviceCredentialStore
{
    private readonly ElevateGateServiceOptions _options;
    private readonly ICredentialProtector _protector;
    private readonly IApprovalApiClient _apiClient;
    private readonly IAuditLog _auditLog;
    private readonly ILogger<DeviceCredentialStore> _logger;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private DeviceCredential? _cached;

    public DeviceCredentialStore(
        IOptions<ElevateGateServiceOptions> options,
        ICredentialProtector protector,
        IApprovalApiClient apiClient,
        IAuditLog auditLog,
        ILogger<DeviceCredentialStore> logger)
    {
        _options = options.Value;
        _protector = protector;
        _apiClient = apiClient;
        _auditLog = auditLog;
        _logger = logger;
    }

    private string CredentialFilePath => Path.Combine(_options.DataDirectory, "device-credential.json");

    public async Task<DeviceCredential> GetOrCreateAsync(CancellationToken cancellationToken = default)
    {
        if (_cached is not null)
            return _cached;

        await _lock.WaitAsync(cancellationToken);
        try
        {
            if (_cached is not null)
                return _cached;

            if (File.Exists(CredentialFilePath))
            {
                _cached = LoadFromDisk();
                return _cached;
            }

            _cached = await EnrollAsync(cancellationToken);
            return _cached;
        }
        finally
        {
            _lock.Release();
        }
    }

    private async Task<DeviceCredential> EnrollAsync(CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(_options.DataDirectory);
        var deviceId = Guid.NewGuid().ToString();

        _logger.LogInformation("Enrolling device {DeviceId} with backend.", deviceId);
        var enrollment = await _apiClient.EnrollAsync(
            new EnrollmentRequest(deviceId, Environment.MachineName, Environment.OSVersion.VersionString),
            cancellationToken);

        var credential = new DeviceCredential(deviceId, enrollment.BearerToken);
        SaveToDisk(credential);

        await _auditLog.RecordAsync(
            new AuditEvent(DateTimeOffset.UtcNow, AuditEventType.DeviceEnrolled, null, deviceId, null, "Device enrolled."),
            cancellationToken);

        return credential;
    }

    private DeviceCredential LoadFromDisk()
    {
        var json = File.ReadAllText(CredentialFilePath);
        var record = JsonSerializer.Deserialize<StoredCredential>(json)
            ?? throw new InvalidOperationException("Device credential file is corrupt.");

        var tokenBytes = _protector.Unprotect(Convert.FromBase64String(record.ProtectedBearerTokenBase64));
        return new DeviceCredential(record.DeviceId, Encoding.UTF8.GetString(tokenBytes));
    }

    private void SaveToDisk(DeviceCredential credential)
    {
        var protectedToken = _protector.Protect(Encoding.UTF8.GetBytes(credential.BearerToken));
        var record = new StoredCredential(credential.DeviceId, Convert.ToBase64String(protectedToken));
        File.WriteAllText(CredentialFilePath, JsonSerializer.Serialize(record));
    }

    private sealed record StoredCredential(string DeviceId, string ProtectedBearerTokenBase64);
}
