using System.Security.Cryptography;
using ElevateGate.Core.Abstractions;

namespace ElevateGate.Service.Security;

/// <summary>
/// Protects the device's bearer credential at rest using Windows DPAPI. Uses
/// <see cref="DataProtectionScope.LocalMachine"/> because the service runs as LocalSystem, not a
/// specific user profile — the credential must be decryptable regardless of which user is
/// (or isn't) logged in.
/// </summary>
public sealed class DpapiCredentialProtector : ICredentialProtector
{
    // Ties the protected blob to this specific use case so it can't be silently reused to
    // decrypt unrelated DPAPI-protected data on the machine, and vice versa.
    private static readonly byte[] Entropy = "ElevateGate.DeviceCredential.v1"u8.ToArray();

    public byte[] Protect(byte[] plaintext) =>
        ProtectedData.Protect(plaintext, Entropy, DataProtectionScope.LocalMachine);

    public byte[] Unprotect(byte[] ciphertext) =>
        ProtectedData.Unprotect(ciphertext, Entropy, DataProtectionScope.LocalMachine);
}
