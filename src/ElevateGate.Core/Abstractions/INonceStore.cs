namespace ElevateGate.Core.Abstractions;

/// <summary>Durable record of every nonce that has ever been presented for validation, to reject replay.</summary>
public interface INonceStore
{
    /// <summary>
    /// Atomically checks whether <paramref name="nonce"/> has been used before and, if not,
    /// records it as used. Returns <c>true</c> only on the first-ever call for a given nonce.
    /// </summary>
    Task<bool> TryConsumeAsync(string nonce, CancellationToken cancellationToken = default);
}
