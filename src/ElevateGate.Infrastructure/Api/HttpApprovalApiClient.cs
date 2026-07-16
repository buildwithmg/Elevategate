using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Models;

namespace ElevateGate.Infrastructure.Api;

/// <summary>
/// Talks to the backend described in docs/API_CONTRACT.md. <see cref="HttpClient.BaseAddress"/>
/// must be configured by the caller (DI); this class owns no transport concerns beyond the
/// contract itself.
/// </summary>
public sealed class HttpApprovalApiClient : IApprovalApiClient
{
    internal static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter(JsonNamingPolicy.CamelCase) },
    };

    private readonly HttpClient _httpClient;

    public HttpApprovalApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<EnrollmentResult> EnrollAsync(EnrollmentRequest request, CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.PostAsJsonAsync("api/v1/enroll", request, JsonOptions, cancellationToken);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<EnrollmentResult>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Enrollment response body was empty.");
    }

    public async Task SubmitRequestAsync(string bearerToken, ApprovalRequest request, CancellationToken cancellationToken = default)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "api/v1/requests")
        {
            Content = JsonContent.Create(request, options: JsonOptions),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);

        using var response = await _httpClient.SendAsync(message, cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    public async Task<IReadOnlyList<ApprovalDecision>> PollDecisionsAsync(
        string bearerToken, string deviceId, DateTimeOffset sinceUtc, CancellationToken cancellationToken = default)
    {
        var url = $"api/v1/devices/{Uri.EscapeDataString(deviceId)}/decisions?since={Uri.EscapeDataString(sinceUtc.ToUniversalTime().ToString("O"))}";
        using var message = new HttpRequestMessage(HttpMethod.Get, url);
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);

        using var response = await _httpClient.SendAsync(message, cancellationToken);
        response.EnsureSuccessStatusCode();

        var decisions = await response.Content.ReadFromJsonAsync<List<ApprovalDecision>>(JsonOptions, cancellationToken);
        return decisions ?? [];
    }

    public async Task<HeartbeatResult> SendHeartbeatAsync(
        string bearerToken, HeartbeatRequest request, CancellationToken cancellationToken = default)
    {
        using var message = new HttpRequestMessage(HttpMethod.Post, "api/v1/heartbeat")
        {
            Content = JsonContent.Create(request, options: JsonOptions),
        };
        message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);

        using var response = await _httpClient.SendAsync(message, cancellationToken);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<HeartbeatResult>(JsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Heartbeat response body was empty.");
    }
}
