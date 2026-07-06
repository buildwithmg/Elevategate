namespace ElevateGate.Core.Validation;

/// <summary>
/// Deterministic Windows-path parsing implemented with plain string operations rather than
/// <see cref="System.IO.Path"/>. The agent only ever runs on Windows, but this logic is
/// security-critical and must behave identically wherever it's compiled and tested — including
/// on a non-Windows dev machine, where <see cref="System.IO.Path"/>'s separator/root semantics
/// differ from Windows and would make tests unrepresentative of production behavior.
/// </summary>
internal static class WindowsPathRules
{
    private static readonly char[] Separators = ['\\', '/'];

    // ':' is included even though it's already implicitly rejected everywhere except the fixed
    // drive-letter position: without this, a segment like "installer.exe:hidden.exe" would
    // canonicalize successfully as an NTFS Alternate Data Stream reference — content hidden
    // behind an ADS name that Win32 will still happily execute directly.
    private static readonly char[] InvalidSegmentChars = ['<', '>', '"', '|', '?', '*', ':', '\0'];

    public static bool IsSeparator(char c) => c == '\\' || c == '/';

    public static bool IsUncOrDeviceLiteral(string path) =>
        path.Length >= 2 && IsSeparator(path[0]) && IsSeparator(path[1]);

    public static bool IsDriveRooted(string path) =>
        path.Length >= 3 &&
        IsAsciiLetter(path[0]) &&
        path[1] == ':' &&
        IsSeparator(path[2]);

    private static bool IsAsciiLetter(char c) => (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');

    public static bool ContainsTraversalSegment(string path)
    {
        foreach (var range in path.Split(Separators, StringSplitOptions.RemoveEmptyEntries))
        {
            if (range == "..")
                return true;
        }
        return false;
    }

    /// <summary>
    /// Canonicalizes an absolute, drive-letter-rooted Windows path with no traversal segments,
    /// no reserved characters, and an upper-cased drive letter. Returns false for anything else
    /// (UNC paths, relative paths, traversal attempts, malformed input) — this validator never
    /// tries to "fix" or resolve suspicious input, only accept-or-reject.
    /// </summary>
    public static bool TryCanonicalize(string rawPath, out string canonicalPath)
    {
        canonicalPath = string.Empty;

        if (string.IsNullOrWhiteSpace(rawPath))
            return false;

        if (!IsDriveRooted(rawPath))
            return false;

        if (ContainsTraversalSegment(rawPath))
            return false;

        var driveLetter = char.ToUpperInvariant(rawPath[0]);
        var rest = rawPath[3..];
        var segments = rest.Split(Separators, StringSplitOptions.RemoveEmptyEntries);

        var cleanSegments = new List<string>(segments.Length);
        foreach (var segment in segments)
        {
            if (segment == ".")
                continue;
            if (segment.IndexOfAny(InvalidSegmentChars) >= 0)
                return false;

            // Win32 silently strips trailing dots/spaces from a path component when actually
            // opening a file, so a segment with one would refer to a different on-disk name than
            // what our canonical string says — reject rather than accept a string that can't be
            // trusted to identify the same file it appears to.
            if (segment.EndsWith('.') || segment.EndsWith(' '))
                return false;

            cleanSegments.Add(segment);
        }

        canonicalPath = cleanSegments.Count == 0
            ? $"{driveLetter}:\\"
            : $"{driveLetter}:\\" + string.Join('\\', cleanSegments);
        return true;
    }

    public static string GetDriveRoot(string canonicalPath) => canonicalPath[..3];
}
