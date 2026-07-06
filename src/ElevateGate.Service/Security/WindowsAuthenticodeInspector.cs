using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;
using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Models;
using Microsoft.Extensions.Logging;

namespace ElevateGate.Service.Security;

/// <summary>
/// Reads Authenticode signer and trust information via WinVerifyTrust. Unsigned or
/// untrusted/revoked files are reported as such — this class never upgrades a weak signal to
/// "trusted" and is never used to auto-approve anything locally; it only informs the backend's
/// decision (see docs/API_CONTRACT.md).
/// </summary>
public sealed class WindowsAuthenticodeInspector : ISignatureInspector
{
    private readonly ILogger<WindowsAuthenticodeInspector> _logger;

    public WindowsAuthenticodeInspector(ILogger<WindowsAuthenticodeInspector> logger)
    {
        _logger = logger;
    }

    public SignatureInfo Inspect(string canonicalFilePath)
    {
        var trustStatus = VerifyTrust(canonicalFilePath, _logger);
        if (trustStatus == SignatureTrustStatus.Unsigned)
            return new SignatureInfo(SignatureTrustStatus.Unsigned, PublisherCommonName: null, CertificateThumbprint: null);

        string? publisher = null;
        string? thumbprint = null;
        try
        {
#pragma warning disable SYSLIB0057 // CreateFromSignedFile remains functional on .NET 8; revisit on the next TFM bump.
            using var certificate = new X509Certificate2(X509Certificate2.CreateFromSignedFile(canonicalFilePath));
#pragma warning restore SYSLIB0057
            publisher = certificate.GetNameInfo(X509NameType.SimpleName, forIssuer: false);
            thumbprint = certificate.Thumbprint;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Could not read signer certificate for {Path}.", canonicalFilePath);
        }

        return new SignatureInfo(trustStatus, publisher, thumbprint);
    }

    private static SignatureTrustStatus VerifyTrust(string filePath, ILogger logger)
    {
        var fileInfoPtr = Marshal.AllocHGlobal(Marshal.SizeOf<NativeMethods.WINTRUST_FILE_INFO>());
        try
        {
            var fileInfo = new NativeMethods.WINTRUST_FILE_INFO
            {
                cbStruct = (uint)Marshal.SizeOf<NativeMethods.WINTRUST_FILE_INFO>(),
                pcwszFilePath = filePath,
                hFile = IntPtr.Zero,
                pgKnownSubject = IntPtr.Zero,
            };
            Marshal.StructureToPtr(fileInfo, fileInfoPtr, false);

            var trustData = new NativeMethods.WINTRUST_DATA
            {
                cbStruct = (uint)Marshal.SizeOf<NativeMethods.WINTRUST_DATA>(),
                dwUIChoice = NativeMethods.WTD_UI_NONE,
                fdwRevocationChecks = NativeMethods.WTD_REVOKE_WHOLECHAIN,
                dwUnionChoice = NativeMethods.WTD_CHOICE_FILE,
                pFile = fileInfoPtr,
                dwStateAction = NativeMethods.WTD_STATEACTION_VERIFY,
                dwProvFlags = NativeMethods.WTD_SAFER_FLAG,
            };

            var actionId = NativeMethods.WINTRUST_ACTION_GENERIC_VERIFY_V2;
            var invalidHandleValue = new IntPtr(-1);
            var result = NativeMethods.WinVerifyTrust(invalidHandleValue, ref actionId, ref trustData);

            // Always release the state WinVerifyTrust allocated, regardless of the verify result.
            trustData.dwStateAction = NativeMethods.WTD_STATEACTION_CLOSE;
            NativeMethods.WinVerifyTrust(invalidHandleValue, ref actionId, ref trustData);

            return result switch
            {
                0 => SignatureTrustStatus.Trusted,
                NativeMethods.TRUST_E_NOSIGNATURE => SignatureTrustStatus.Unsigned,
                NativeMethods.CERT_E_REVOKED => SignatureTrustStatus.Revoked,
                NativeMethods.TRUST_E_BAD_DIGEST => SignatureTrustStatus.HashMismatch,
                NativeMethods.TRUST_E_EXPLICIT_DISTRUST => SignatureTrustStatus.Untrusted,
                NativeMethods.TRUST_E_SUBJECT_NOT_TRUSTED => SignatureTrustStatus.Untrusted,
                _ => SignatureTrustStatus.Unknown,
            };
        }
        catch (Exception ex)
        {
            logger.LogWarning(ex, "WinVerifyTrust call failed for {Path}.", filePath);
            return SignatureTrustStatus.Unknown;
        }
        finally
        {
            Marshal.FreeHGlobal(fileInfoPtr);
        }
    }
}
