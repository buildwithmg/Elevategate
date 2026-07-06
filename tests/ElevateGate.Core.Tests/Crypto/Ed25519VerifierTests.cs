using ElevateGate.Core.Crypto;

namespace ElevateGate.Core.Tests.Crypto;

public class Ed25519VerifierTests
{
    [Fact]
    public void ValidSignature_IsAccepted()
    {
        var (publicKey, privateKey) = Ed25519KeyPairGenerator.Generate();
        var message = "the message"u8.ToArray();
        var signature = Ed25519KeyPairGenerator.Sign(privateKey, message);

        var result = new Ed25519Verifier().Verify(publicKey, message, signature);

        Assert.True(result);
    }

    [Fact]
    public void TamperedMessage_IsRejected()
    {
        var (publicKey, privateKey) = Ed25519KeyPairGenerator.Generate();
        var signature = Ed25519KeyPairGenerator.Sign(privateKey, "original"u8.ToArray());

        var result = new Ed25519Verifier().Verify(publicKey, "tampered"u8.ToArray(), signature);

        Assert.False(result);
    }

    [Fact]
    public void WrongPublicKey_IsRejected()
    {
        var (_, privateKey) = Ed25519KeyPairGenerator.Generate();
        var (otherPublicKey, _) = Ed25519KeyPairGenerator.Generate();
        var message = "the message"u8.ToArray();
        var signature = Ed25519KeyPairGenerator.Sign(privateKey, message);

        var result = new Ed25519Verifier().Verify(otherPublicKey, message, signature);

        Assert.False(result);
    }

    [Fact]
    public void MalformedKeyLength_IsRejectedNotThrown()
    {
        var result = new Ed25519Verifier().Verify(new byte[4], "x"u8.ToArray(), new byte[64]);

        Assert.False(result);
    }

    [Fact]
    public void MalformedSignatureLength_IsRejectedNotThrown()
    {
        var (publicKey, _) = Ed25519KeyPairGenerator.Generate();

        var result = new Ed25519Verifier().Verify(publicKey, "x"u8.ToArray(), new byte[3]);

        Assert.False(result);
    }
}
