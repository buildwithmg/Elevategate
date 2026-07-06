namespace ElevateGate.Service.Enrollment;

public interface IDeviceCredentialStore
{
    /// <summary>Returns the cached device credential, enrolling with the backend on first run if needed.</summary>
    Task<DeviceCredential> GetOrCreateAsync(CancellationToken cancellationToken = default);
}
