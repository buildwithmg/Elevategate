using System.Diagnostics;
using System.IO.Compression;
using System.IO.Pipes;
using ElevateGate.Core.Update;
using ElevateGate.Service.Options;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Update;

/// <summary>
/// Downloads and installs a newer release once <see cref="SelfUpdateWorker"/> has decided one is
/// available. Only ever called with a release this same process already confirmed is newer -
/// this class doesn't re-check anything, it just applies.
/// </summary>
public sealed class SelfUpdateApplier
{
    private readonly HttpClient _httpClient;
    private readonly ElevateGateServiceOptions _options;
    private readonly ILogger<SelfUpdateApplier> _logger;

    public SelfUpdateApplier(
        HttpClient httpClient, IOptions<ElevateGateServiceOptions> options, ILogger<SelfUpdateApplier> logger)
    {
        _httpClient = httpClient;
        _options = options.Value;
        _logger = logger;
    }

    public async Task ApplyAsync(GitHubRelease release, CancellationToken cancellationToken)
    {
        var stagingDir = Path.Combine(_options.DataDirectory, "update-staging");
        if (Directory.Exists(stagingDir))
            Directory.Delete(stagingDir, recursive: true);
        Directory.CreateDirectory(stagingDir);

        var zipPath = Path.Combine(stagingDir, "update.zip");
        _logger.LogInformation("Downloading update {Tag} from {Url}.", release.TagName, release.ZipDownloadUrl);

        await using (var httpStream = await _httpClient.GetStreamAsync(release.ZipDownloadUrl, cancellationToken))
        await using (var fileStream = File.Create(zipPath))
        {
            await httpStream.CopyToAsync(fileStream, cancellationToken);
        }

        var extractedDir = Path.Combine(stagingDir, "extracted");
        ZipFile.ExtractToDirectory(zipPath, extractedDir, overwriteFiles: true);

        var installDir = Path.GetDirectoryName(Environment.ProcessPath)
            ?? throw new InvalidOperationException("Could not determine this process's own install directory.");

        // Deliberately does not touch appsettings.json - it holds this deployment's real
        // enrollment key/backend URL/public key, not the release's blank template.
        SwapExecutable(extractedDir, installDir, "ElevateGate.Service.exe");
        SwapExecutable(extractedDir, installDir, "ElevateGate.Tray.exe");

        _logger.LogInformation("Update {Tag} installed to {InstallDir}.", release.TagName, installDir);

        TrySignalTrayRestart();
        ScheduleServiceRestart();
    }

    /// <summary>
    /// Renames (not deletes) the currently-installed exe before copying the new one into place.
    /// Windows allows renaming a file that's currently executing - the process running it keeps
    /// working fine against its existing handle to the renamed copy - which is what makes this
    /// safe to do while that very exe might be running as this or another process.
    /// </summary>
    private void SwapExecutable(string extractedDir, string installDir, string exeName)
    {
        var newExe = Path.Combine(extractedDir, exeName);
        if (!File.Exists(newExe))
        {
            _logger.LogWarning("Update package did not contain {ExeName}; leaving the current build in place.", exeName);
            return;
        }

        var currentExe = Path.Combine(installDir, exeName);
        var backupExe = currentExe + ".old";

        if (File.Exists(backupExe))
        {
            try { File.Delete(backupExe); }
            catch (IOException) { /* leftover from a previous update, still locked - harmless, skip it */ }
        }

        if (File.Exists(currentExe))
            File.Move(currentExe, backupExe);

        File.Copy(newExe, currentExe, overwrite: true);
    }

    /// <summary>Best-effort - if no tray is running for any logged-in user right now, it'll pick
    /// up the new build the next time it's launched regardless, so a failure here is fine.</summary>
    private static void TrySignalTrayRestart()
    {
        try
        {
            using var pipe = new NamedPipeClientStream(".", TrayActivationProtocol.PipeName, PipeDirection.Out);
            pipe.Connect(2000);
            using var writer = new StreamWriter(pipe) { AutoFlush = true };
            writer.WriteLine(TrayActivationProtocol.RestartForUpdateSentinel);
        }
        catch (Exception)
        {
        }
    }

    /// <summary>
    /// This process is about to stop itself (SelfUpdateWorker calls IHostApplicationLifetime
    /// .StopApplication() right after ApplyAsync returns) - nothing running inside it can restart
    /// it afterward, so a short-lived detached helper does that instead.
    /// </summary>
    private void ScheduleServiceRestart()
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = $"/c timeout /t 3 /nobreak >nul & sc stop \"{_options.ServiceName}\" & sc start \"{_options.ServiceName}\"",
            UseShellExecute = false,
            CreateNoWindow = true,
        });
    }
}
