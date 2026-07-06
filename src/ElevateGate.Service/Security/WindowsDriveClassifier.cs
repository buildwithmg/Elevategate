using ElevateGate.Core.Validation;

namespace ElevateGate.Service.Security;

/// <summary>Real, Windows-only drive-type lookup backing <see cref="PathValidator"/>.</summary>
public sealed class WindowsDriveClassifier : IDriveClassifier
{
    public DriveClassification Classify(string driveRoot)
    {
        try
        {
            var driveInfo = new DriveInfo(driveRoot);
            return driveInfo.DriveType switch
            {
                DriveType.Removable => DriveClassification.Removable,
                DriveType.Network => DriveClassification.Network,
                DriveType.Fixed => DriveClassification.Fixed,
                _ => DriveClassification.Unknown,
            };
        }
        catch
        {
            // An unrecognized or inaccessible drive root is never treated as safe-by-default.
            return DriveClassification.Unknown;
        }
    }
}
