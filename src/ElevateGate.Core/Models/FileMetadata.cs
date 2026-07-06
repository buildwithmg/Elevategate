namespace ElevateGate.Core.Models;

/// <summary>Facts about a candidate executable, always derived server-side by the service — never trusted from the tray.</summary>
public sealed record FileMetadata(
    string FileName,
    string FullPath,
    long SizeBytes,
    string? FileVersion,
    string Sha256Hex);
