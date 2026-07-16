import { CreateGroupDialog } from "@/components/device-groups/create-group-dialog";
import { GroupsTable } from "@/components/device-groups/groups-table";
import { Card, CardContent } from "@/components/ui/card";

export default function DeviceGroupsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Device Groups</h1>
          <p className="text-sm text-muted-foreground">
            Organize devices and scope app-allowlist entries to a specific group.
          </p>
        </div>
        <CreateGroupDialog />
      </div>
      <Card>
        <CardContent>
          <GroupsTable />
        </CardContent>
      </Card>
    </div>
  );
}
