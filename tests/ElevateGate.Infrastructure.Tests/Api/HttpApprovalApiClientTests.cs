using System.Net;
using System.Net.Http.Json;
using ElevateGate.Core.Models;
using ElevateGate.Infrastructure.Api;
using ElevateGate.Infrastructure.Tests.TestSupport;

namespace ElevateGate.Infrastructure.Tests.Api;

public class HttpApprovalApiClientTests
{
    private static HttpClient CreateClient(StubHttpMessageHandler handler) =>
        new(handler) { BaseAddress = new Uri("https://elevategate.example.internal/") };

    [Fact]
    public async Task EnrollAsync_PostsRequestAndParsesResponse()
    {
        var handler = new StubHttpMessageHandler(request =>
        {
            Assert.Equal(HttpMethod.Post, request.Method);
            Assert.Equal("/api/v1/enroll", request.RequestUri!.AbsolutePath);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = JsonContent.Create(new { bearerToken = "token-abc", enrolledAtUtc = "2026-01-01T00:00:00Z" }),
            };
        });
        var client = new HttpApprovalApiClient(CreateClient(handler));

        var result = await client.EnrollAsync(new EnrollmentRequest("device-1", "WORKSTATION-1", "Windows 11 23H2"));

        Assert.Equal("token-abc", result.BearerToken);
        Assert.NotNull(handler.LastRequestBody);
        Assert.Contains("device-1", handler.LastRequestBody);
    }

    [Fact]
    public async Task SubmitRequestAsync_SendsBearerTokenAndBody()
    {
        var handler = new StubHttpMessageHandler(request =>
        {
            Assert.Equal("Bearer", request.Headers.Authorization?.Scheme);
            Assert.Equal("token-abc", request.Headers.Authorization?.Parameter);
            return new HttpResponseMessage(HttpStatusCode.Accepted);
        });
        var client = new HttpApprovalApiClient(CreateClient(handler));
        var request = new ApprovalRequest(
            "req-1",
            "device-1",
            new FileMetadata("installer.exe", @"C:\Temp\installer.exe", 1024, "1.0.0", new string('a', 64)),
            new SignatureInfo(SignatureTrustStatus.Trusted, "Contoso Ltd.", "thumbprint"),
            "Need to install a driver",
            DateTimeOffset.UtcNow);

        await client.SubmitRequestAsync("token-abc", request);

        Assert.Contains("installer.exe", handler.LastRequestBody);
        Assert.Contains("Contoso Ltd.", handler.LastRequestBody);
    }

    [Fact]
    public async Task PollDecisionsAsync_ParsesApprovedAndDeniedDecisions()
    {
        const string json =
            """
            [
              {
                "requestId": "req-1",
                "status": "approved",
                "token": {
                  "deviceId": "device-1",
                  "requestId": "req-1",
                  "sha256Hex": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                  "expiresAtUtc": "2030-01-01T00:00:00Z",
                  "nonce": "nonce-1",
                  "signature": "AQIDBA=="
                }
              },
              {
                "requestId": "req-2",
                "status": "denied",
                "token": null
              }
            ]
            """;
        var handler = new StubHttpMessageHandler(request =>
        {
            Assert.Equal(HttpMethod.Get, request.Method);
            Assert.StartsWith("/api/v1/devices/device-1/decisions", request.RequestUri!.AbsolutePath + request.RequestUri.Query);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
            };
        });
        var client = new HttpApprovalApiClient(CreateClient(handler));

        var decisions = await client.PollDecisionsAsync("token-abc", "device-1", DateTimeOffset.UnixEpoch);

        Assert.Equal(2, decisions.Count);
        var approved = decisions.Single(d => d.RequestId == "req-1");
        Assert.Equal(RequestStatus.Approved, approved.Status);
        Assert.NotNull(approved.Token);
        Assert.Equal(new byte[] { 1, 2, 3, 4 }, approved.Token!.Signature);

        var denied = decisions.Single(d => d.RequestId == "req-2");
        Assert.Equal(RequestStatus.Denied, denied.Status);
        Assert.Null(denied.Token);
    }

    [Fact]
    public async Task SendHeartbeatAsync_PostsTelemetryAndParsesUpdateRequested()
    {
        var handler = new StubHttpMessageHandler(request =>
        {
            Assert.Equal(HttpMethod.Post, request.Method);
            Assert.Equal("/api/v1/heartbeat", request.RequestUri!.AbsolutePath);
            Assert.Equal("Bearer", request.Headers.Authorization?.Scheme);
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = JsonContent.Create(new { updateRequested = true }),
            };
        });
        var client = new HttpApprovalApiClient(CreateClient(handler));
        var request = new HeartbeatRequest("1.0.3", 500_000_000_000, 100_000_000_000, 16_000_000_000, 8_000_000_000);

        var result = await client.SendHeartbeatAsync("token-abc", request);

        Assert.True(result.UpdateRequested);
        Assert.NotNull(handler.LastRequestBody);
        Assert.Contains("1.0.3", handler.LastRequestBody);
        Assert.Contains("diskTotalBytes", handler.LastRequestBody);
    }
}
