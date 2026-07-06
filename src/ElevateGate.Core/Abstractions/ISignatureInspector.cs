using ElevateGate.Core.Models;

namespace ElevateGate.Core.Abstractions;

/// <summary>Reads Authenticode signer/trust information for a file. Windows-only implementation lives in ElevateGate.Service.</summary>
public interface ISignatureInspector
{
    SignatureInfo Inspect(string canonicalFilePath);
}
