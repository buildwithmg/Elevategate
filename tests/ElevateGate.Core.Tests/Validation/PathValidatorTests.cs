using ElevateGate.Core.Tests.TestSupport;
using ElevateGate.Core.Validation;

namespace ElevateGate.Core.Tests.Validation;

public class PathValidatorTests
{
    [Fact]
    public void OrdinaryLocalPath_IsAccepted()
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(@"C:\Program Files\Vendor\installer.exe");

        Assert.True(outcome.IsValid);
        Assert.Equal(@"C:\Program Files\Vendor\installer.exe", outcome.CanonicalPath);
    }

    [Theory]
    [InlineData(@"C:\Temp\..\Windows\System32\evil.exe")]
    [InlineData(@"C:\Temp\..\..\evil.exe")]
    [InlineData(@"..\evil.exe")]
    public void TraversalSegments_AreRejected(string path)
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(path);

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.Traversal, outcome.Reason);
    }

    [Theory]
    [InlineData(@"\\fileserver\share\installer.exe")]
    [InlineData(@"//fileserver/share/installer.exe")]
    public void UncPaths_AreRejected(string path)
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(path);

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.UncOrNetworkPath, outcome.Reason);
    }

    [Fact]
    public void MappedNetworkDrive_IsRejected()
    {
        var classifier = new FakeDriveClassifier().With(@"Z:\", DriveClassification.Network);
        var validator = new PathValidator(classifier);

        var outcome = validator.Validate(@"Z:\shared\installer.exe");

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.UncOrNetworkPath, outcome.Reason);
    }

    [Fact]
    public void UnknownDriveType_IsRejectedByDefault()
    {
        var classifier = new FakeDriveClassifier().With(@"D:\", DriveClassification.Unknown);
        var validator = new PathValidator(classifier);

        var outcome = validator.Validate(@"D:\installer.exe");

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.UnsupportedDrive, outcome.Reason);
    }

    [Fact]
    public void RemovableDrive_IsRejected()
    {
        var classifier = new FakeDriveClassifier().With(@"E:\", DriveClassification.Removable);
        var validator = new PathValidator(classifier);

        var outcome = validator.Validate(@"E:\installer.exe");

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.RemovableDrive, outcome.Reason);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("relative\\path.exe")]
    [InlineData("not-a-path-at-all")]
    public void MalformedOrRelativePaths_AreRejected(string path)
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(path);

        Assert.False(outcome.IsValid);
    }

    [Fact]
    public void ReservedCharactersInSegment_AreRejected()
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate("C:\\Temp\\bad|name.exe");

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.Malformed, outcome.Reason);
    }

    [Fact]
    public void AlternateDataStreamSyntax_IsRejected()
    {
        // "installer.exe:hidden.exe" would refer to an NTFS Alternate Data Stream, not the
        // plain file — a known technique for hiding executable content behind an innocuous name.
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(@"C:\Temp\installer.exe:hidden.exe");

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.Malformed, outcome.Reason);
    }

    [Theory]
    [InlineData(@"C:\Temp\installer.exe.")]
    [InlineData(@"C:\Temp\installer.exe ")]
    public void TrailingDotOrSpaceInSegment_IsRejected(string path)
    {
        // Win32 silently strips a trailing dot/space when actually opening the file, so a
        // canonical string carrying one wouldn't reliably identify the same on-disk file.
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(path);

        Assert.False(outcome.IsValid);
        Assert.Equal(PathRejectionReason.Malformed, outcome.Reason);
    }

    [Fact]
    public void DotSegments_AreNormalizedAway()
    {
        var validator = new PathValidator(new FakeDriveClassifier(DriveClassification.Fixed));

        var outcome = validator.Validate(@"C:\Temp\.\installer.exe");

        Assert.True(outcome.IsValid);
        Assert.Equal(@"C:\Temp\installer.exe", outcome.CanonicalPath);
    }
}
