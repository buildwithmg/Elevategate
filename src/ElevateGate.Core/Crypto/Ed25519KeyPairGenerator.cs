using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;
using Org.BouncyCastle.Security;
using BcEd25519KeyPairGenerator = Org.BouncyCastle.Crypto.Generators.Ed25519KeyPairGenerator;

namespace ElevateGate.Core.Crypto;

/// <summary>
/// Ed25519 key generation and signing. The agent itself never signs anything — this exists for
/// tests and for a future backend/CLI tool that provisions the server keypair and issues tokens.
/// </summary>
public static class Ed25519KeyPairGenerator
{
    public static (byte[] PublicKey, byte[] PrivateKey) Generate()
    {
        var generator = new BcEd25519KeyPairGenerator();
        generator.Init(new Ed25519KeyGenerationParameters(new SecureRandom()));
        var pair = generator.GenerateKeyPair();

        var priv = (Ed25519PrivateKeyParameters)pair.Private;
        var pub = (Ed25519PublicKeyParameters)pair.Public;
        return (pub.GetEncoded(), priv.GetEncoded());
    }

    public static byte[] Sign(byte[] privateKey, byte[] message)
    {
        var signer = new Ed25519Signer();
        signer.Init(forSigning: true, new Ed25519PrivateKeyParameters(privateKey, 0));
        signer.BlockUpdate(message, 0, message.Length);
        return signer.GenerateSignature();
    }
}
