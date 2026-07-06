using ElevateGate.Core.Hashing;

namespace ElevateGate.Core.Tests.Hashing;

public class Sha256FileHasherTests
{
    [Fact]
    public async Task KnownVector_ProducesExpectedHash()
    {
        // Independently-verified SHA-256("hello world"), not derived from the BCL call under test.
        const string expectedHash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9";
        using var stream = new MemoryStream(System.Text.Encoding.UTF8.GetBytes("hello world"));

        var actual = await Sha256FileHasher.ComputeHexAsync(stream);

        Assert.Equal(expectedHash, actual);
    }

    [Fact]
    public async Task FileOnDisk_HashesCorrectly()
    {
        var tempFile = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString("N") + ".bin");
        try
        {
            var content = new byte[] { 1, 2, 3, 4, 5 };
            await File.WriteAllBytesAsync(tempFile, content);
            var expected = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(content)).ToLowerInvariant();

            var actual = await Sha256FileHasher.ComputeHexAsync(tempFile);

            Assert.Equal(expected, actual);
        }
        finally
        {
            File.Delete(tempFile);
        }
    }

    [Fact]
    public async Task ChangedContent_ProducesDifferentHash()
    {
        using var original = new MemoryStream(System.Text.Encoding.UTF8.GetBytes("version-1"));
        using var changed = new MemoryStream(System.Text.Encoding.UTF8.GetBytes("version-2"));

        var hash1 = await Sha256FileHasher.ComputeHexAsync(original);
        var hash2 = await Sha256FileHasher.ComputeHexAsync(changed);

        Assert.NotEqual(hash1, hash2);
    }
}
