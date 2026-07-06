import { DevicesTable } from "@/components/devices/devices-table";
import { Card, CardContent } from "@/components/ui/card";

export default function DevicesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Devices</h1>
        <p className="text-sm text-muted-foreground">Windows endpoints enrolled with ElevateGate.</p>
      </div>
      <Card>
        <CardContent>
          <DevicesTable />
        </CardContent>
      </Card>
    </div>
  );
}
