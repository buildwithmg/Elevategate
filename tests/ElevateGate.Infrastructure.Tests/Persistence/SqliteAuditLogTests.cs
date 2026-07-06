using ElevateGate.Core.Abstractions;
using ElevateGate.Infrastructure.Persistence;
using Microsoft.Data.Sqlite;

namespace ElevateGate.Infrastructure.Tests.Persistence;

public class SqliteAuditLogTests : IDisposable
{
    private readonly string _dbPath = Path.Combine(Path.GetTempPath(), $"elevategate-audit-tests-{Guid.NewGuid():N}.db");

    [Fact]
    public async Task RecordAsync_PersistsEvent()
    {
        var log = new SqliteAuditLog(_dbPath);
        var auditEvent = new AuditEvent(DateTimeOffset.UtcNow, AuditEventType.RequestSubmitted, "req-1", "device-1", "nonce-1", "submitted");

        await log.RecordAsync(auditEvent);

        Assert.Equal(1, CountRows());
    }

    [Fact]
    public async Task RecordAsync_AllowsNullCorrelationFields()
    {
        var log = new SqliteAuditLog(_dbPath);
        var auditEvent = new AuditEvent(DateTimeOffset.UtcNow, AuditEventType.DeviceEnrolled, null, null, null, "enrolled");

        await log.RecordAsync(auditEvent);

        Assert.Equal(1, CountRows());
    }

    private int CountRows()
    {
        using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = _dbPath }.ToString());
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM AuditEvents;";
        return Convert.ToInt32(command.ExecuteScalar());
    }

    public void Dispose()
    {
        if (File.Exists(_dbPath))
            File.Delete(_dbPath);
    }
}
