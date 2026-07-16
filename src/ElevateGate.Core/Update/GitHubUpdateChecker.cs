using System.Text.Json;

namespace ElevateGate.Core.Update;

/// <summary>
/// Checks GitHub Releases for a newer build of this agent. Read-only against a public API
/// endpoint - never authenticates, never writes anything. Applying an update (replacing files,
/// restarting processes) is a separate, deliberately more privileged concern - see
/// ElevateGate.Service.Update.SelfUpdateApplier.
/// </summary>
public sealed class GitHubUpdateChecker
{
    private readonly HttpClient _httpClient;

    public GitHubUpdateChecker(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    /// <summary>
    /// Fetches the latest release for <paramref name="ownerSlashRepo"/> (e.g.
    /// "buildwithmg/Elevategate") and finds the win-x64 agent zip asset. Returns null on any
    /// failure (network error, non-success status, missing/malformed fields, no matching asset)
    /// - a broken or unreachable update channel must never surface as an exception that could
    /// disrupt the caller's actual job (polling for approvals).
    /// </summary>
    public async Task<GitHubRelease?> GetLatestReleaseAsync(string ownerSlashRepo, CancellationToken cancellationToken = default)
    {
        try
        {
            using var request = new HttpRequestMessage(
                HttpMethod.Get, $"https://api.github.com/repos/{ownerSlashRepo}/releases/latest");
            request.Headers.UserAgent.ParseAdd("ElevateGate-Agent-Updater");

            using var response = await _httpClient.SendAsync(request, cancellationToken);
            if (!response.IsSuccessStatusCode)
                return null;

            using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
            using var document = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);
            var root = document.RootElement;

            if (!root.TryGetProperty("tag_name", out var tagNameProp))
                return null;
            var tagName = tagNameProp.GetString();
            if (string.IsNullOrWhiteSpace(tagName))
                return null;

            if (!root.TryGetProperty("assets", out var assetsProp))
                return null;

            foreach (var asset in assetsProp.EnumerateArray())
            {
                var name = asset.TryGetProperty("name", out var nameProp) ? nameProp.GetString() : null;
                if (name is null) continue;
                if (!name.StartsWith("ElevateGate-Agent-", StringComparison.OrdinalIgnoreCase)) continue;
                if (!name.EndsWith("-win-x64.zip", StringComparison.OrdinalIgnoreCase)) continue;

                var downloadUrl = asset.TryGetProperty("browser_download_url", out var urlProp)
                    ? urlProp.GetString()
                    : null;
                if (string.IsNullOrWhiteSpace(downloadUrl)) continue;

                return new GitHubRelease(tagName, downloadUrl);
            }

            return null;
        }
        catch (Exception)
        {
            return null;
        }
    }

    /// <summary>
    /// True iff <paramref name="tagName"/> (e.g. "v1.0.2", "1.0.2") parses to a version strictly
    /// greater than <paramref name="currentVersion"/>. An unparsable tag is treated as "not
    /// newer" (fail closed - never auto-update off a malformed/unexpected tag).
    /// </summary>
    public static bool IsNewer(Version currentVersion, string tagName)
    {
        var trimmed = tagName.TrimStart('v', 'V');
        return Version.TryParse(trimmed, out var latest) && latest > currentVersion;
    }
}
