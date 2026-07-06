using ElevateGate.Core.Abstractions;
using Microsoft.Data.Sqlite;

namespace ElevateGate.Infrastructure.Persistence;

/// <summary>Append-only local audit trail backed by SQLite. Rows are never updated or deleted by the agent.</summary>
public sealed class SqliteAuditLog : IAuditLog
{
    private readonly string _connectionString;

    public SqliteAuditLog(string databasePath)
    {
        _connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
        Initialize();
    }

    private void Initialize()
    {
        using var connection = new SqliteConnection(_connectionString);
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            CREATE TABLE IF NOT EXISTS AuditEvents (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                TimestampUtc TEXT NOT NULL,
                EventType TEXT NOT NULL,
                RequestId TEXT NULL,
                DeviceId TEXT NULL,
                Nonce TEXT NULL,
                Message TEXT NOT NULL
            );
            """;
        command.ExecuteNonQuery();
    }

    public async Task RecordAsync(AuditEvent auditEvent, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(auditEvent);

        await using var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText =
            """
            INSERT INTO AuditEvents (TimestampUtc, EventType, RequestId, DeviceId, Nonce, Message)
            VALUES ($timestamp, $eventType, $requestId, $deviceId, $nonce, $message);
            """;
        command.Parameters.AddWithValue("$timestamp", auditEvent.TimestampUtc.ToString("O"));
        command.Parameters.AddWithValue("$eventType", auditEvent.EventType.ToString());
        command.Parameters.AddWithValue("$requestId", (object?)auditEvent.RequestId ?? DBNull.Value);
        command.Parameters.AddWithValue("$deviceId", (object?)auditEvent.DeviceId ?? DBNull.Value);
        command.Parameters.AddWithValue("$nonce", (object?)auditEvent.Nonce ?? DBNull.Value);
        command.Parameters.AddWithValue("$message", auditEvent.Message);

        await command.ExecuteNonQueryAsync(cancellationToken);
    }
}
