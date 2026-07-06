using ElevateGate.Core.Validation;

namespace ElevateGate.Core.Tests.TestSupport;

public sealed class FakeDriveClassifier : IDriveClassifier
{
    private readonly Dictionary<string, DriveClassification> _map = new(StringComparer.OrdinalIgnoreCase);
    private readonly DriveClassification _default;

    public FakeDriveClassifier(DriveClassification defaultClassification = DriveClassification.Fixed)
    {
        _default = defaultClassification;
    }

    public FakeDriveClassifier With(string driveRoot, DriveClassification classification)
    {
        _map[driveRoot] = classification;
        return this;
    }

    public DriveClassification Classify(string driveRoot) =>
        _map.TryGetValue(driveRoot, out var classification) ? classification : _default;
}
