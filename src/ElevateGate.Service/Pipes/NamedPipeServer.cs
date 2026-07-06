using System.IO.Pipes;
using System.Text;
using System.Text.Json;
using ElevateGate.Core.Ipc;
using ElevateGate.Service.Options;
using ElevateGate.Service.RequestTracking;
using ElevateGate.Service.Security;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ElevateGate.Service.Pipes;

/// <summary>
/// The only channel the tray can reach the service through. Accepts exactly one newline-delimited
/// JSON request per connection, from a client that passes <see cref="PipeClientValidator"/>, and
/// dispatches strictly to <see cref="RequestCoordinator.SubmitAsync"/> or
/// <see cref="RequestCoordinator.GetStatus"/> — there is no other message type and no path from
/// here to arbitrary command execution.
/// </summary>
public sealed class NamedPipeServer : BackgroundService
{
    private readonly ElevateGateServiceOptions _options;
    private readonly PipeClientValidator _clientValidator;
    private readonly RequestCoordinator _requestCoordinator;
    private readonly ILogger<NamedPipeServer> _logger;

    public NamedPipeServer(
        IOptions<ElevateGateServiceOptions> options,
        PipeClientValidator clientValidator,
        RequestCoordinator requestCoordinator,
        ILogger<NamedPipeServer> logger)
    {
        _options = options.Value;
        _clientValidator = clientValidator;
        _requestCoordinator = requestCoordinator;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            NamedPipeServerStream? pipe = null;
            try
            {
                pipe = CreateServerStream();
                await pipe.WaitForConnectionAsync(stoppingToken);

                if (!_clientValidator.IsAuthorized(pipe))
                {
                    _logger.LogWarning("Rejected unauthorized named pipe connection attempt.");
                    continue;
                }

                await HandleConnectionAsync(pipe, stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (IOException ex)
            {
                _logger.LogWarning(ex, "Named pipe I/O error; recreating pipe instance.");
            }
            finally
            {
                pipe?.Dispose();
            }
        }
    }

    private async Task HandleConnectionAsync(NamedPipeServerStream pipe, CancellationToken cancellationToken)
    {
        using var reader = new StreamReader(pipe, Encoding.UTF8, leaveOpen: true);
        using var writer = new StreamWriter(pipe, Encoding.UTF8, leaveOpen: true) { AutoFlush = true };

        var line = await reader.ReadLineAsync(cancellationToken);
        if (line is null)
            return;

        var response = await DispatchAsync(line, cancellationToken);
        await writer.WriteLineAsync(JsonSerializer.Serialize(response));
    }

    private async Task<PipeResponseMessage> DispatchAsync(string line, CancellationToken cancellationToken)
    {
        PipeRequestMessage? request;
        try
        {
            request = JsonSerializer.Deserialize<PipeRequestMessage>(line);
        }
        catch (JsonException)
        {
            return new PipeResponseMessage(false, null, null, "Malformed request.");
        }

        if (request is null)
            return new PipeResponseMessage(false, null, null, "Malformed request.");

        return request.Type switch
        {
            PipeMessageType.SubmitRequest => await _requestCoordinator.SubmitAsync(request.FilePath, request.Reason, cancellationToken),
            PipeMessageType.GetStatus => _requestCoordinator.GetStatus(request.RequestId),
            _ => new PipeResponseMessage(false, null, null, "Unknown message type."),
        };
    }

    private NamedPipeServerStream CreateServerStream() =>
        SecuredNamedPipeFactory.CreateServerInstance(_options.PipeName);
}
