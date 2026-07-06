using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;

namespace ElevateGate.Core.Crypto;

/// <summary>
/// Verifies Ed25519 signatures over approval payloads. This is the ONLY cryptographic trust
/// decision the agent makes about a server-issued decision; it must never throw on malformed
/// input — malformed input is simply an invalid signature.
/// </summary>
public sealed class Ed25519Verifier
{
    public const int PublicKeyLength = 32;
    public const int SignatureLength = 64;

    public bool Verify(ReadOnlySpan<byte> publicKey, ReadOnlySpan<byte> message, ReadOnlySpan<byte> signature)
    {
        if (publicKey.Length != PublicKeyLength || signature.Length != SignatureLength)
            return false;

        try
        {
            var verifier = new Ed25519Signer();
            verifier.Init(forSigning: false, new Ed25519PublicKeyParameters(publicKey.ToArray(), 0));
            var messageBytes = message.ToArray();
            verifier.BlockUpdate(messageBytes, 0, messageBytes.Length);
            return verifier.VerifySignature(signature.ToArray());
        }
        catch
        {
            // Any malformed key/signature material is treated as a failed verification, never an exception.
            return false;
        }
    }
}
