namespace ElevateGate.Core.Abstractions;

/// <summary>
/// Encrypts/decrypts the device's bearer credential at rest. The real implementation
/// (ElevateGate.Service) uses Windows DPAPI with LocalMachine scope, since the service runs as
/// LocalSystem. Never handles or stores administrator passwords — only the device's own
/// backend-issued bearer token.
/// </summary>
public interface ICredentialProtector
{
    byte[] Protect(byte[] plaintext);
    byte[] Unprotect(byte[] ciphertext);
}
