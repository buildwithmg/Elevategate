using ElevateGate.Core.Models;

namespace ElevateGate.Core.Abstractions;

/// <summary>HTTP client contract against the backend described in docs/API_CONTRACT.md.</summary>
public interface IApprovalApiClient
{
    Task<EnrollmentResult> EnrollAsync(EnrollmentRequest request, CancellationToken cancellationToken = default);

    Task SubmitRequestAsync(string bearerToken, ApprovalRequest request, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<ApprovalDecision>> PollDecisionsAsync(
        string bearerToken, string deviceId, DateTimeOffset sinceUtc, CancellationToken cancellationToken = default);

    Task<HeartbeatResult> SendHeartbeatAsync(
        string bearerToken, HeartbeatRequest request, CancellationToken cancellationToken = default);
}
