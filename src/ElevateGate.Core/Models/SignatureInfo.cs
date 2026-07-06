namespace ElevateGate.Core.Models;

public enum SignatureTrustStatus
{
    /// <summary>File has no Authenticode signature at all.</summary>
    Unsigned,
    /// <summary>Signed and the chain validates to a trusted root.</summary>
    Trusted,
    /// <summary>Signed but the chain does not validate (e.g. untrusted/expired/revoked root).</summary>
    Untrusted,
    /// <summary>The embedded signature hash does not match the file's actual content.</summary>
    HashMismatch,
    /// <summary>Signing certificate has been revoked.</summary>
    Revoked,
    /// <summary>Trust status could not be determined.</summary>
    Unknown,
}

/// <summary>Authenticode signer details exposed to the backend as part of an approval request. Never used locally to auto-approve anything.</summary>
public sealed record SignatureInfo(
    SignatureTrustStatus TrustStatus,
    string? PublisherCommonName,
    string? CertificateThumbprint);
