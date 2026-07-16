using ElevateGate.Core.Models;
using Microsoft.Extensions.Logging;

namespace ElevateGate.Service.Telemetry;

/// <summary>
/// Reads local disk/RAM stats for the periodic heartbeat. Every field is best-effort - a stat
/// this process can't read for any reason is simply omitted (null), never fabricated, and never
/// allowed to throw out of <see cref="Collect"/> itself.
/// </summary>
public sealed class SystemTelemetryCollector
{
    private readonly ILogger<SystemTelemetryCollector> _logger;

    public SystemTelemetryCollector(ILogger<SystemTelemetryCollector> logger)
    {
        _logger = logger;
    }

    public HeartbeatRequest Collect()
    {
        var (diskTotal, diskFree) = ReadDiskStats();
        var (ramTotal, ramUsed) = ReadRamStats();
        var agentVersion = typeof(SystemTelemetryCollector).Assembly.GetName().Version?.ToString();

        return new HeartbeatRequest(agentVersion, diskTotal, diskFree, ramTotal, ramUsed);
    }

    private (long? total, long? free) ReadDiskStats()
    {
        try
        {
            var systemRoot = Path.GetPathRoot(Environment.SystemDirectory);
            if (string.IsNullOrEmpty(systemRoot))
                return (null, null);

            var drive = new DriveInfo(systemRoot);
            return (drive.TotalSize, drive.AvailableFreeSpace);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read disk telemetry.");
            return (null, null);
        }
    }

    private (long? total, long? used) ReadRamStats()
    {
        try
        {
            var status = new NativeMethods.MEMORYSTATUSEX();
            status.dwLength = (uint)System.Runtime.InteropServices.Marshal.SizeOf<NativeMethods.MEMORYSTATUSEX>();

            if (!NativeMethods.GlobalMemoryStatusEx(ref status))
            {
                _logger.LogWarning("GlobalMemoryStatusEx failed (Win32 error {Error}).",
                    System.Runtime.InteropServices.Marshal.GetLastWin32Error());
                return (null, null);
            }

            var total = (long)status.ullTotalPhys;
            var used = total - (long)status.ullAvailPhys;
            return (total, used);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read RAM telemetry.");
            return (null, null);
        }
    }
}
