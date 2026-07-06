using ElevateGate.Core.Abstractions;
using Microsoft.Data.Sqlite;

namespace ElevateGate.Infrastructure.Persistence;

/// <summary>
/// Durable, file-backed nonce ledger. A nonce that has ever been consumed stays rejected across
/// service restarts — replay protection must not reset on reboot.
/// </summary>
public sealed class SqliteNonceStore : INonceStore
{
    private readonly string _connectionString;

    public SqliteNonceStore(string databasePath)
    {
        _connectionString = new SqliteConnectionStringBuilder { DataSource = databasePath }.ToString();
        Initialize();
    }

    private void Initialize()
    {
        using var connection = OpenConnection();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            CREATE TABLE IF NOT EXISTS ConsumedNonces (
                Nonce TEXT PRIMARY KEY NOT NULL,
                ConsumedAtUtc TEXT NOT NULL
            );
            """;
        command.ExecuteNonQuery();
    }

    public async Task<bool> TryConsumeAsync(string nonce, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrEmpty(nonce);

        await using var connection = await OpenConnectionAsync(cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = "INSERT OR IGNORE INTO ConsumedNonces (Nonce, ConsumedAtUtc) VALUES ($nonce, $now);";
        command.Parameters.AddWithValue("$nonce", nonce);
        command.Parameters.AddWithValue("$now", DateTimeOffset.UtcNow.ToString("O"));

        var rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
        return rowsAffected == 1;
    }

    private SqliteConnection OpenConnection()
    {
        var connection = new SqliteConnection(_connectionString);
        connection.Open();
        ApplyBusyTimeout(connection);
        return connection;
    }

    private async Task<SqliteConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        var connection = new SqliteConnection(_connectionString);
        await connection.OpenAsync(cancellationToken);
        ApplyBusyTimeout(connection);
        return connection;
    }

    private static void ApplyBusyTimeout(SqliteConnection connection)
    {
        using var pragma = connection.CreateCommand();
        pragma.CommandText = "PRAGMA busy_timeout = 5000;";
        pragma.ExecuteNonQuery();
    }
}
