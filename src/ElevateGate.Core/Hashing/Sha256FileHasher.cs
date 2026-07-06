using System.Security.Cryptography;

namespace ElevateGate.Core.Hashing;

/// <summary>Streams a file through SHA-256 without buffering it fully in memory.</summary>
public static class Sha256FileHasher
{
    public static async Task<string> ComputeHexAsync(string filePath, CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(
            filePath, FileMode.Open, FileAccess.Read, FileShare.Read, bufferSize: 81920, useAsync: true);
        return await ComputeHexAsync(stream, cancellationToken);
    }

    public static async Task<string> ComputeHexAsync(Stream stream, CancellationToken cancellationToken = default)
    {
        var hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
