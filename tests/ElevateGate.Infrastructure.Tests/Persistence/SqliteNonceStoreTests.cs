using ElevateGate.Infrastructure.Persistence;

namespace ElevateGate.Infrastructure.Tests.Persistence;

public class SqliteNonceStoreTests : IDisposable
{
    private readonly string _dbPath = Path.Combine(Path.GetTempPath(), $"elevategate-nonce-tests-{Guid.NewGuid():N}.db");

    [Fact]
    public async Task FirstUse_IsAccepted()
    {
        var store = new SqliteNonceStore(_dbPath);

        var consumed = await store.TryConsumeAsync("nonce-1");

        Assert.True(consumed);
    }

    [Fact]
    public async Task SecondUse_OfSameNonce_IsRejected()
    {
        var store = new SqliteNonceStore(_dbPath);

        var first = await store.TryConsumeAsync("nonce-1");
        var second = await store.TryConsumeAsync("nonce-1");

        Assert.True(first);
        Assert.False(second);
    }

    [Fact]
    public async Task Reuse_IsRejectedAcrossStoreInstances()
    {
        // Simulates the service restarting: replay protection must survive that, since it's
        // backed by a file, not in-memory state.
        var firstInstance = new SqliteNonceStore(_dbPath);
        await firstInstance.TryConsumeAsync("nonce-durable");

        var secondInstance = new SqliteNonceStore(_dbPath);
        var reused = await secondInstance.TryConsumeAsync("nonce-durable");

        Assert.False(reused);
    }

    [Fact]
    public async Task DifferentNonces_AreIndependentlyTracked()
    {
        var store = new SqliteNonceStore(_dbPath);

        var a = await store.TryConsumeAsync("nonce-a");
        var b = await store.TryConsumeAsync("nonce-b");

        Assert.True(a);
        Assert.True(b);
    }

    public void Dispose()
    {
        if (File.Exists(_dbPath))
            File.Delete(_dbPath);
    }
}
