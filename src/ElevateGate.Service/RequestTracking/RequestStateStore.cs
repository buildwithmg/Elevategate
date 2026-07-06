using System.Collections.Concurrent;
using ElevateGate.Core.Models;

namespace ElevateGate.Service.RequestTracking;

/// <summary>
/// In-memory record of requests this service instance has submitted, so the tray's GetStatus
/// poll and the backend polling worker have something to read/update. Not persisted: a service
/// restart mid-request loses tracking for it, which is an accepted MVP limitation (see
/// docs/DEVELOPMENT.md) — the backend remains the durable source of truth for the decision itself.
/// </summary>
public sealed class RequestStateStore
{
    private readonly ConcurrentDictionary<string, TrackedRequest> _requests = new();

    public void Add(string requestId, TrackedRequest request) => _requests[requestId] = request;

    public TrackedRequest? Get(string requestId) => _requests.GetValueOrDefault(requestId);

    public void UpdateStatus(string requestId, RequestStatus status)
    {
        _requests.AddOrUpdate(
            requestId,
            _ => throw new InvalidOperationException($"Cannot update unknown request '{requestId}'."),
            (_, existing) => existing with { Status = status });
    }
}
