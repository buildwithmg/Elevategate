using System.Runtime.InteropServices;

namespace ElevateGate.Service.Telemetry;

/// <summary>P/Invoke surface for reading system RAM usage. No other Win32 calls belong here - see
/// Security/NativeMethods.cs for the (unrelated) Authenticode/named-pipe P/Invoke surface.</summary>
internal static partial class NativeMethods
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct MEMORYSTATUSEX
    {
        public uint dwLength;
        public uint dwMemoryLoad;
        public ulong ullTotalPhys;
        public ulong ullAvailPhys;
        public ulong ullTotalPageFile;
        public ulong ullAvailPageFile;
        public ulong ullTotalVirtual;
        public ulong ullAvailVirtual;
        public ulong ullAvailExtendedVirtual;
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static partial bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX lpBuffer);
}
