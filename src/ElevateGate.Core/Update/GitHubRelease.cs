namespace ElevateGate.Core.Update;

/// <summary>The subset of a GitHub Releases API response the updater actually needs.</summary>
public sealed record GitHubRelease(string TagName, string ZipDownloadUrl);
