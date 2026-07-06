using ElevateGate.Core.Abstractions;
using ElevateGate.Core.Validation;
using ElevateGate.Infrastructure.Api;
using ElevateGate.Infrastructure.Persistence;
using ElevateGate.Service.Enrollment;
using ElevateGate.Service.Execution;
using ElevateGate.Service.Options;
using ElevateGate.Service.Pipes;
using ElevateGate.Service.RequestTracking;
using ElevateGate.Service.Security;
using ElevateGate.Service.Workers;
using Microsoft.Extensions.Hosting.WindowsServices;
using Serilog;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddWindowsService(o => o.ServiceName = "ElevateGate Agent");

builder.Services.Configure<ElevateGateServiceOptions>(builder.Configuration.GetSection(ElevateGateServiceOptions.SectionName));
var serviceOptions = builder.Configuration
    .GetSection(ElevateGateServiceOptions.SectionName)
    .Get<ElevateGateServiceOptions>() ?? new ElevateGateServiceOptions();

Directory.CreateDirectory(serviceOptions.DataDirectory);

builder.Services.AddSerilog((_, loggerConfiguration) =>
{
    loggerConfiguration
        .MinimumLevel.Information()
        .Enrich.FromLogContext()
        .WriteTo.File(
            Path.Combine(serviceOptions.DataDirectory, "logs", "elevategate-.log"),
            rollingInterval: RollingInterval.Day,
            retainedFileCountLimit: 30);

    if (WindowsServiceHelpers.IsWindowsService())
        loggerConfiguration.WriteTo.EventLog("ElevateGate Agent", manageEventSource: true);
});

builder.Services.AddSingleton<INonceStore>(_ =>
    new SqliteNonceStore(Path.Combine(serviceOptions.DataDirectory, "nonces.db")));
builder.Services.AddSingleton<IAuditLog>(_ =>
    new SqliteAuditLog(Path.Combine(serviceOptions.DataDirectory, "audit.db")));

builder.Services.AddSingleton<ICredentialProtector, DpapiCredentialProtector>();
builder.Services.AddSingleton<IDriveClassifier, WindowsDriveClassifier>();
builder.Services.AddSingleton<ISignatureInspector, WindowsAuthenticodeInspector>();
builder.Services.AddSingleton<PathValidator>();

builder.Services.AddSingleton(_ =>
{
    var publicKeyBase64 = serviceOptions.ServerPublicKeyBase64;
    if (string.IsNullOrWhiteSpace(publicKeyBase64))
        throw new InvalidOperationException(
            $"{ElevateGateServiceOptions.SectionName}:{nameof(ElevateGateServiceOptions.ServerPublicKeyBase64)} must be configured.");

    return Convert.FromBase64String(publicKeyBase64);
});
builder.Services.AddSingleton(sp => new ApprovalTokenValidator(
    sp.GetRequiredService<byte[]>(),
    sp.GetRequiredService<INonceStore>()));

builder.Services.AddHttpClient<IApprovalApiClient, HttpApprovalApiClient>(client =>
{
    client.BaseAddress = new Uri(serviceOptions.BackendBaseUrl);
    client.Timeout = TimeSpan.FromSeconds(30);
});

builder.Services.AddSingleton<IDeviceCredentialStore, DeviceCredentialStore>();
builder.Services.AddSingleton<RequestStateStore>();
builder.Services.AddSingleton<RequestCoordinator>();
builder.Services.AddSingleton<ExecutionEngine>();
builder.Services.AddSingleton<PipeClientValidator>();

builder.Services.AddHostedService<NamedPipeServer>();
builder.Services.AddHostedService<ApprovalPollingWorker>();

var host = builder.Build();
host.Run();
