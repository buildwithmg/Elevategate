import { AuditLogTable } from "@/components/audit-logs/audit-log-table";
import { Card, CardContent } from "@/components/ui/card";

export default function AuditLogsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit Logs</h1>
        <p className="text-sm text-muted-foreground">
          Every enrollment, review decision, and approval consumption.
        </p>
      </div>
      <Card>
        <CardContent>
          <AuditLogTable />
        </CardContent>
      </Card>
    </div>
  );
}
