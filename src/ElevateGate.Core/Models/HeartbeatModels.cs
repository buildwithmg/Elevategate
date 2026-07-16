namespace ElevateGate.Core.Models;

/// <summary>
/// Periodic system telemetry sent to POST /api/v1/heartbeat - not part of the agent's originally
/// -shipped contract, added so the dashboard can show live disk/RAM usage and the agent's own
/// running version per device. All fields nullable: a machine this agent can't read a stat from
/// simply omits it rather than sending a fabricated value.
/// </summary>
public sealed record HeartbeatRequest(
    string? AgentVersion,
    long? DiskTotalBytes,
    long? DiskFreeBytes,
    long? RamTotalBytes,
    long? RamUsedBytes);

/// <summary>`UpdateRequested` mirrors an admin's POST /api/v1/devices/{id}/request-update on the
/// dashboard - true tells the service to check for/apply an update right away.</summary>
public sealed record HeartbeatResult(bool UpdateRequested);
