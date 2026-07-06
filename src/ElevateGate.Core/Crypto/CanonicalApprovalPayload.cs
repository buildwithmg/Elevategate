using System.Text;

namespace ElevateGate.Core.Crypto;

/// <summary>
/// Builds the exact byte sequence that the backend signs (and the agent verifies) for an
/// approval token. Uses length-prefixed fields rather than a delimited string so that no
/// field value — however it's produced upstream — can ever be crafted to shift a boundary
/// and change the meaning of another field.
/// </summary>
public static class CanonicalApprovalPayload
{
    /// <summary>Bump if the signed field set or encoding ever changes; old and new versions must never verify against each other.</summary>
    public const byte SchemaVersion = 1;

    public static byte[] Build(string deviceId, string requestId, string sha256Hex, DateTimeOffset expiresAtUtc, string nonce)
    {
        ArgumentNullException.ThrowIfNull(deviceId);
        ArgumentNullException.ThrowIfNull(requestId);
        ArgumentNullException.ThrowIfNull(sha256Hex);
        ArgumentNullException.ThrowIfNull(nonce);

        using var buffer = new MemoryStream();
        buffer.WriteByte(SchemaVersion);
        WriteField(buffer, deviceId);
        WriteField(buffer, requestId);
        WriteField(buffer, sha256Hex.ToLowerInvariant());
        WriteField(buffer, expiresAtUtc.ToUniversalTime().ToString("O"));
        WriteField(buffer, nonce);
        return buffer.ToArray();
    }

    private static void WriteField(Stream stream, string value)
    {
        var bytes = Encoding.UTF8.GetBytes(value);
        if (bytes.Length > ushort.MaxValue)
            throw new ArgumentOutOfRangeException(nameof(value), "Field too long to encode in canonical payload.");

        Span<byte> lengthPrefix = stackalloc byte[2];
        System.Buffers.Binary.BinaryPrimitives.WriteUInt16BigEndian(lengthPrefix, (ushort)bytes.Length);
        stream.Write(lengthPrefix);
        stream.Write(bytes);
    }
}
