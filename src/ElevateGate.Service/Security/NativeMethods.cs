using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace ElevateGate.Service.Security;

/// <summary>P/Invoke surface for Authenticode verification and named-pipe client identification. No other Win32 calls belong here.</summary>
internal static partial class NativeMethods
{
    // --- WinTrust / Authenticode ---

    internal static readonly Guid WINTRUST_ACTION_GENERIC_VERIFY_V2 = new("00AAC56B-CD44-11d0-8CC2-00C04FC295EE");

    internal const uint WTD_UI_NONE = 2;
    internal const uint WTD_REVOKE_WHOLECHAIN = 1;
    internal const uint WTD_CHOICE_FILE = 1;
    internal const uint WTD_STATEACTION_VERIFY = 1;
    internal const uint WTD_STATEACTION_CLOSE = 2;
    internal const uint WTD_SAFER_FLAG = 0x100;

    internal const int TRUST_E_NOSIGNATURE = unchecked((int)0x800B0100);
    internal const int TRUST_E_EXPLICIT_DISTRUST = unchecked((int)0x800B0111);
    internal const int TRUST_E_SUBJECT_NOT_TRUSTED = unchecked((int)0x800B0004);
    internal const int CERT_E_REVOKED = unchecked((int)0x800B010C);
    internal const int TRUST_E_BAD_DIGEST = unchecked((int)0x80096010);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    internal struct WINTRUST_FILE_INFO
    {
        public uint cbStruct;
        public string pcwszFilePath;
        public IntPtr hFile;
        public IntPtr pgKnownSubject;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct WINTRUST_DATA
    {
        public uint cbStruct;
        public IntPtr pPolicyCallbackData;
        public IntPtr pSIPClientData;
        public uint dwUIChoice;
        public uint fdwRevocationChecks;
        public uint dwUnionChoice;
        public IntPtr pFile;
        public uint dwStateAction;
        public IntPtr hWVTStateData;
        public IntPtr pwszURLReference;
        public uint dwProvFlags;
        public uint dwUIContext;
        public IntPtr pSignatureSettings;
    }

    [LibraryImport("wintrust.dll", SetLastError = true)]
    internal static partial int WinVerifyTrust(IntPtr hwnd, ref Guid pgActionID, ref WINTRUST_DATA pWVTData);

    // --- Named pipe client identification ---

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool GetNamedPipeClientProcessId(SafeHandle pipe, out uint clientProcessId);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool GetNamedPipeClientSessionId(SafeHandle pipe, out uint clientSessionId);

    [LibraryImport("kernel32.dll")]
    internal static partial uint WTSGetActiveConsoleSessionId();

    // --- Named pipe creation with an explicit security descriptor ---
    // (Deliberately hand-rolled via CreateNamedPipe + an SDDL descriptor rather than the
    // System.IO.Pipes.AccessControl NuGet package: that package hasn't shipped a release
    // targeting anything past net5.0 and its type resolution is unreliable when this project
    // is cross-compiled from a non-Windows dev machine. This gives the same strict-ACL
    // guarantee with no extra dependency.)

    internal const uint PIPE_ACCESS_DUPLEX = 0x00000003;
    internal const uint FILE_FLAG_OVERLAPPED = 0x40000000;
    internal const uint PIPE_TYPE_BYTE = 0x00000000;
    internal const uint PIPE_READMODE_BYTE = 0x00000000;
    internal const uint PIPE_REJECT_REMOTE_CLIENTS = 0x00000008;
    internal const uint PIPE_UNLIMITED_INSTANCES = 255;
    internal const uint SDDL_REVISION_1 = 1;

    /// <summary>Grants read/write to interactive local users and full control to LocalSystem only.</summary>
    internal const string PipeSecurityDescriptorSddl = "D:(A;;GRGW;;;IU)(A;;GA;;;SY)";

    [StructLayout(LayoutKind.Sequential)]
    internal struct SECURITY_ATTRIBUTES
    {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        public int bInheritHandle;
    }

    [LibraryImport("advapi32.dll", EntryPoint = "ConvertStringSecurityDescriptorToSecurityDescriptorW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool ConvertStringSecurityDescriptorToSecurityDescriptor(
        string stringSecurityDescriptor, uint stringSDRevision, out IntPtr securityDescriptor, out uint securityDescriptorSize);

    [LibraryImport("kernel32.dll")]
    internal static partial IntPtr LocalFree(IntPtr hMem);

    [LibraryImport("kernel32.dll", EntryPoint = "CreateNamedPipeW", StringMarshalling = StringMarshalling.Utf16, SetLastError = true)]
    internal static partial SafePipeHandle CreateNamedPipe(
        string lpName,
        uint dwOpenMode,
        uint dwPipeMode,
        uint nMaxInstances,
        uint nOutBufferSize,
        uint nInBufferSize,
        uint nDefaultTimeOut,
        ref SECURITY_ATTRIBUTES lpSecurityAttributes);
}
