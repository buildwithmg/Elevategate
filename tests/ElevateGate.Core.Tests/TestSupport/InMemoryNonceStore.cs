using System.Collections.Concurrent;
using ElevateGate.Core.Abstractions;

namespace ElevateGate.Core.Tests.TestSupport;

public sealed class InMemoryNonceStore : INonceStore
{
    private readonly ConcurrentDictionary<string, byte> _seen = new();

    public Task<bool> TryConsumeAsync(string nonce, CancellationToken cancellationToken = default) =>
        Task.FromResult(_seen.TryAdd(nonce, 0));
}
