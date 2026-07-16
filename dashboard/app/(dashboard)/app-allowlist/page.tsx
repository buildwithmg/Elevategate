import { AllowlistTable } from "@/components/app-allowlist/allowlist-table";
import { CreateEntryDialog } from "@/components/app-allowlist/create-entry-dialog";
import { Card, CardContent } from "@/components/ui/card";

export default function AppAllowlistPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">App Allowlist</h1>
          <p className="text-sm text-muted-foreground">
            Apps that auto-approve without a human request — every auto-approval is still recorded
            in the audit log.
          </p>
        </div>
        <CreateEntryDialog />
      </div>
      <Card>
        <CardContent>
          <AllowlistTable />
        </CardContent>
      </Card>
    </div>
  );
}
