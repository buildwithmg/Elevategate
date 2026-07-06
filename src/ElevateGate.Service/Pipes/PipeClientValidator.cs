using System.Diagnostics;
using System.IO.Pipes;
using ElevateGate.Service.Options;
using ElevateGate.Service.Security;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Pipes;

/// <summary>
/// Confirms a connecting named-pipe client is genuinely the installed ElevateGate.Tray.exe,
/// running in the currently active console session — not just any authenticated local process
/// that happened to be allowed to open the pipe by ACL.
/// </summary>
public sealed class PipeClientValidator
{
    private readonly ElevateGateServiceOptions _options;
    private readonly ILogger<PipeClientValidator> _logger;

    public PipeClientValidator(IOptions<ElevateGateServiceOptions> options, ILogger<PipeClientValidator> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public bool IsAuthorized(NamedPipeServerStream pipe)
    {
        try
        {
            if (!NativeMethods.GetNamedPipeClientProcessId(pipe.SafePipeHandle, out var processId))
            {
                _logger.LogWarning("Could not resolve named pipe client process id.");
                return false;
            }

            if (!NativeMethods.GetNamedPipeClientSessionId(pipe.SafePipeHandle, out var sessionId))
            {
                _logger.LogWarning("Could not resolve named pipe client session id.");
                return false;
            }

            var activeConsoleSessionId = NativeMethods.WTSGetActiveConsoleSessionId();
            if (sessionId != activeConsoleSessionId)
            {
                _logger.LogWarning(
                    "Rejected pipe client in session {SessionId}; active console session is {ActiveSessionId}.",
                    sessionId, activeConsoleSessionId);
                return false;
            }

            using var process = Process.GetProcessById((int)processId);
            var imagePath = process.MainModule?.FileName;
            if (!string.Equals(imagePath, _options.ExpectedTrayExecutablePath, StringComparison.OrdinalIgnoreCase))
            {
                _logger.LogWarning("Rejected pipe client with unexpected image path {ImagePath}.", imagePath);
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Named pipe client validation failed.");
            return false;
        }
    }
}
