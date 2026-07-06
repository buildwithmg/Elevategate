using System.ComponentModel;
using System.IO.Pipes;
using System.Runtime.InteropServices;

namespace ElevateGate.Service.Security;

/// <summary>Creates a named pipe server instance with an explicit, minimal DACL — see <see cref="NativeMethods.PipeSecurityDescriptorSddl"/>.</summary>
public static class SecuredNamedPipeFactory
{
    public static NamedPipeServerStream CreateServerInstance(string pipeName)
    {
        if (!NativeMethods.ConvertStringSecurityDescriptorToSecurityDescriptor(
                NativeMethods.PipeSecurityDescriptorSddl, NativeMethods.SDDL_REVISION_1,
                out var securityDescriptorPtr, out _))
        {
            throw new Win32Exception(Marshal.GetLastPInvokeError());
        }

        try
        {
            var securityAttributes = new NativeMethods.SECURITY_ATTRIBUTES
            {
                nLength = Marshal.SizeOf<NativeMethods.SECURITY_ATTRIBUTES>(),
                lpSecurityDescriptor = securityDescriptorPtr,
                bInheritHandle = 0,
            };

            var handle = NativeMethods.CreateNamedPipe(
                $@"\\.\pipe\{pipeName}",
                NativeMethods.PIPE_ACCESS_DUPLEX | NativeMethods.FILE_FLAG_OVERLAPPED,
                NativeMethods.PIPE_TYPE_BYTE | NativeMethods.PIPE_READMODE_BYTE | NativeMethods.PIPE_REJECT_REMOTE_CLIENTS,
                NativeMethods.PIPE_UNLIMITED_INSTANCES,
                nOutBufferSize: 4096,
                nInBufferSize: 4096,
                nDefaultTimeOut: 0,
                ref securityAttributes);

            if (handle.IsInvalid)
                throw new Win32Exception(Marshal.GetLastPInvokeError());

            return new NamedPipeServerStream(PipeDirection.InOut, isAsync: true, isConnected: false, handle);
        }
        finally
        {
            NativeMethods.LocalFree(securityDescriptorPtr);
        }
    }
}
