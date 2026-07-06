using ElevateGate.Core.Models;

namespace ElevateGate.Service.RequestTracking;

public sealed record TrackedRequest(string CanonicalPath, string Reason, DateTimeOffset SubmittedAtUtc, RequestStatus Status);
