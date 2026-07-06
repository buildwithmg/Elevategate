namespace ElevateGate.Core.Validation;

/// <summary>
/// Classifies the drive a canonical path root (e.g. <c>"C:\"</c>) lives on. The real
/// implementation (backed by <c>System.IO.DriveInfo</c>) lives in ElevateGate.Service, since
/// drive enumeration is a Windows runtime concern; this abstraction lets <see cref="PathValidator"/>
/// be tested with simulated removable/network/fixed drives on any platform.
/// </summary>
public interface IDriveClassifier
{
    DriveClassification Classify(string driveRoot);
}
