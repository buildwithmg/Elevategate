using System.Diagnostics;
using ElevateGate.Core.Hashing;
using ElevateGate.Core.Models;
using ElevateGate.Core.Validation;
using Microsoft.Extensions.Logging;

namespace ElevateGate.Service.Execution;

/// <summary>
/// The only place in the entire codebase that ever starts a process. Independently re-derives
/// and re-checks everything — path validity, file existence, current SHA-256, and full token
/// validation (signature/device/expiry/nonce/hash) — rather than trusting any decision made
/// earlier in the pipeline. This closes the gap between "approval was decided" and "file is
/// about to run," which can be minutes apart.
/// </summary>
public sealed class ExecutionEngine
{
    private static readonly HashSet<string> AllowedExtensions = new(StringComparer.OrdinalIgnoreCase) { ".exe", ".msi" };

    private readonly PathValidator _pathValidator;
    private readonly ApprovalTokenValidator _tokenValidator;
    private readonly ILogger<ExecutionEngine> _logger;

    public ExecutionEngine(PathValidator pathValidator, ApprovalTokenValidator tokenValidator, ILogger<ExecutionEngine> logger)
    {
        _pathValidator = pathValidator;
        _tokenValidator = tokenValidator;
        _logger = logger;
    }

    /// <param name="expectedRequestId">
    /// The id of the specific request this execution is for — the ground truth, independent of
    /// whatever <paramref name="token"/> claims. Passing this through and checking it inside
    /// <see cref="ApprovalTokenValidator"/> is what stops a token from being cross-applied to a
    /// different pending request that happens to reference a file with identical content (and
    /// therefore an identical SHA-256).
    /// </param>
    public async Task<ExecutionOutcome> ExecuteAsync(
        ApprovalToken token, string expectedRequestId, string rawPath, string deviceId, CancellationToken cancellationToken)
    {
        var pathOutcome = _pathValidator.Validate(rawPath);
        if (!pathOutcome.IsValid)
        {
            _logger.LogWarning(
                "Execution blocked: path rejected ({Reason}) for request {RequestId}.", pathOutcome.Reason, expectedRequestId);
            return ExecutionOutcome.Failed($"Path rejected: {pathOutcome.Reason}");
        }

        var canonicalPath = pathOutcome.CanonicalPath!;
        var extension = Path.GetExtension(canonicalPath);
        if (!AllowedExtensions.Contains(extension))
        {
            _logger.LogWarning(
                "Execution blocked: unsupported extension '{Extension}' for request {RequestId}.", extension, expectedRequestId);
            return ExecutionOutcome.Failed("Unsupported file type.");
        }

        if (!File.Exists(canonicalPath))
        {
            _logger.LogWarning(
                "Execution blocked: file no longer exists at '{Path}' for request {RequestId}.", canonicalPath, expectedRequestId);
            return ExecutionOutcome.Failed("File not found.");
        }

        var currentHash = await Sha256FileHasher.ComputeHexAsync(canonicalPath, cancellationToken);

        var validation = await _tokenValidator.ValidateAsync(token, deviceId, expectedRequestId, currentHash, cancellationToken);
        if (!validation.IsValid)
        {
            _logger.LogWarning(
                "Execution blocked: token rejected ({Reason}) for request {RequestId}.", validation.Reason, expectedRequestId);
            return ExecutionOutcome.Failed($"Token rejected: {validation.Reason}");
        }

        return await LaunchAsync(canonicalPath, extension, expectedRequestId, cancellationToken);
    }

    private async Task<ExecutionOutcome> LaunchAsync(
        string canonicalPath, string extension, string requestId, CancellationToken cancellationToken)
    {
        var startInfo = extension.Equals(".msi", StringComparison.OrdinalIgnoreCase)
            ? BuildMsiExecStartInfo(canonicalPath)
            : new ProcessStartInfo(canonicalPath) { UseShellExecute = false };

        try
        {
            using var process = Process.Start(startInfo);
            if (process is null)
            {
                _logger.LogError("Process.Start returned null for request {RequestId}.", requestId);
                return ExecutionOutcome.Failed("Failed to start process.");
            }

            _logger.LogInformation(
                "Started '{Path}' for request {RequestId} (pid {ProcessId}).", canonicalPath, requestId, process.Id);
            await process.WaitForExitAsync(cancellationToken);
            _logger.LogInformation(
                "Process for request {RequestId} exited with code {ExitCode}.", requestId, process.ExitCode);

            return ExecutionOutcome.Ok();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Execution failed for request {RequestId}.", requestId);
            return ExecutionOutcome.Failed(ex.Message);
        }
    }

    private static ProcessStartInfo BuildMsiExecStartInfo(string canonicalMsiPath)
    {
        var startInfo = new ProcessStartInfo("msiexec.exe") { UseShellExecute = false };
        // Fixed flags only — the verified path is the sole variable. No argument here, or
        // anywhere else in this method, is ever sourced from the tray, backend, or token.
        startInfo.ArgumentList.Add("/i");
        startInfo.ArgumentList.Add(canonicalMsiPath);
        startInfo.ArgumentList.Add("/quiet");
        return startInfo;
    }
}
