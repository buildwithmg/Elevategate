namespace ElevateGate.Core.Models;

/// <summary>Identity of this endpoint as known to the backend, established at enrollment.</summary>
public sealed record DeviceInfo(
    string DeviceId,
    string MachineName,
    string OperatingSystemVersion,
    DateTimeOffset EnrolledAtUtc);
