using System.Net;
using ElevateGate.Core.Tests.TestSupport;
using ElevateGate.Core.Update;

namespace ElevateGate.Core.Tests.Update;

public class GitHubUpdateCheckerTests
{
    [Theory]
    [InlineData("1.0.0", "v1.0.1", true)]
    [InlineData("1.0.0", "1.0.1", true)]
    [InlineData("1.0.1", "v1.0.1", false)]
    [InlineData("1.0.2", "v1.0.1", false)]
    [InlineData("1.0.0", "v2.0.0", true)]
    [InlineData("1.0.0", "not-a-version", false)]
    [InlineData("1.0.0", "", false)]
    public void IsNewer_ComparesVersionsCorrectly(string current, string tag, bool expected)
    {
        Assert.Equal(expected, GitHubUpdateChecker.IsNewer(Version.Parse(current), tag));
    }

    [Fact]
    public async Task GetLatestReleaseAsync_ParsesTagAndMatchingZipAsset()
    {
        const string json =
            """
            {
              "tag_name": "v1.0.3",
              "assets": [
                { "name": "diag-probe.exe", "browser_download_url": "https://example.test/diag-probe.exe" },
                { "name": "ElevateGate-Agent-v1.0.3-win-x64.zip", "browser_download_url": "https://example.test/agent.zip" }
              ]
            }
            """;
        var handler = new StubHttpMessageHandler(request =>
        {
            Assert.Equal("https://api.github.com/repos/buildwithmg/Elevategate/releases/latest", request.RequestUri!.ToString());
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
            };
        });
        var checker = new GitHubUpdateChecker(new HttpClient(handler));

        var release = await checker.GetLatestReleaseAsync("buildwithmg/Elevategate");

        Assert.NotNull(release);
        Assert.Equal("v1.0.3", release!.TagName);
        Assert.Equal("https://example.test/agent.zip", release.ZipDownloadUrl);
    }

    [Fact]
    public async Task GetLatestReleaseAsync_ReturnsNullWhenNoMatchingAsset()
    {
        const string json =
            """
            {
              "tag_name": "v1.0.3",
              "assets": [
                { "name": "diag-probe.exe", "browser_download_url": "https://example.test/diag-probe.exe" }
              ]
            }
            """;
        var handler = new StubHttpMessageHandler(_ => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
        });
        var checker = new GitHubUpdateChecker(new HttpClient(handler));

        var release = await checker.GetLatestReleaseAsync("buildwithmg/Elevategate");

        Assert.Null(release);
    }

    [Fact]
    public async Task GetLatestReleaseAsync_ReturnsNullOnNonSuccessStatus()
    {
        var handler = new StubHttpMessageHandler(_ => new HttpResponseMessage(HttpStatusCode.NotFound));
        var checker = new GitHubUpdateChecker(new HttpClient(handler));

        var release = await checker.GetLatestReleaseAsync("buildwithmg/Elevategate");

        Assert.Null(release);
    }

    [Fact]
    public async Task GetLatestReleaseAsync_ReturnsNullOnNetworkFailure()
    {
        var handler = new StubHttpMessageHandler(_ => throw new HttpRequestException("network down"));
        var checker = new GitHubUpdateChecker(new HttpClient(handler));

        var release = await checker.GetLatestReleaseAsync("buildwithmg/Elevategate");

        Assert.Null(release);
    }
}
