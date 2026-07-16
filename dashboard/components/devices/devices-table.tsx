"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState, ErrorState } from "@/components/shared/state-views";
import { DeviceGroupSelect } from "@/components/devices/device-group-select";
import { UpdateNowButton } from "@/components/devices/update-now-button";
import { listDevices } from "@/lib/api-client";
import type { Device } from "@/lib/schemas";
import { cn, formatBytesGB, formatUsagePercent } from "@/lib/utils";

function OnlineBadge({ online }: { online: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          online ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600",
        )}
      />
      {online ? "Online" : "Offline"}
    </span>
  );
}

function EnrollmentBadge({ status }: { status: "active" | "revoked" }) {
  return (
    <Badge
      variant="outline"
      className={
        status === "active"
          ? "border-emerald-300 bg-emerald-100 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
          : "border-red-300 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
      }
    >
      {status === "active" ? "Active" : "Revoked"}
    </Badge>
  );
}

function DiskCell({ device }: { device: Device }) {
  if (device.disk_total_bytes === null || device.disk_free_bytes === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const used = device.disk_total_bytes - device.disk_free_bytes;
  const usedPct = formatUsagePercent(used, device.disk_total_bytes);
  const isLow = device.disk_total_bytes > 0 && device.disk_free_bytes / device.disk_total_bytes < 0.1;
  return (
    <span className={cn("text-sm", isLow && "font-medium text-red-600 dark:text-red-400")}>
      {formatBytesGB(device.disk_free_bytes)} free of {formatBytesGB(device.disk_total_bytes)} ({usedPct} used)
    </span>
  );
}

function RamCell({ device }: { device: Device }) {
  if (device.ram_total_bytes === null || device.ram_used_bytes === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const usedPct = formatUsagePercent(device.ram_used_bytes, device.ram_total_bytes);
  const isHigh = device.ram_used_bytes / device.ram_total_bytes > 0.9;
  return (
    <span className={cn("text-sm", isHigh && "font-medium text-amber-600 dark:text-amber-400")}>
      {usedPct} of {formatBytesGB(device.ram_total_bytes)}
    </span>
  );
}

export function DevicesTable() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["devices"],
    queryFn: () => listDevices({ limit: 200 }),
    refetchInterval: 15000,
  });

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load devices."}
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        title="No devices enrolled yet"
        description="Devices appear here once the ElevateGate agent enrolls them."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Hostname</TableHead>
          <TableHead>Device UUID</TableHead>
          <TableHead>Operating System</TableHead>
          <TableHead>Agent Version</TableHead>
          <TableHead>Group</TableHead>
          <TableHead>Disk</TableHead>
          <TableHead>RAM</TableHead>
          <TableHead>Last Seen</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Enrollment</TableHead>
          <TableHead>Update</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((device) => (
          <TableRow key={device.id}>
            <TableCell className="font-medium">{device.hostname}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">
              {device.device_uuid}
            </TableCell>
            <TableCell>{device.operating_system}</TableCell>
            <TableCell>{device.agent_version ?? "—"}</TableCell>
            <TableCell>
              <DeviceGroupSelect deviceId={device.id} groupId={device.group_id} />
            </TableCell>
            <TableCell>
              <DiskCell device={device} />
            </TableCell>
            <TableCell>
              <RamCell device={device} />
            </TableCell>
            <TableCell className="text-muted-foreground">
              {device.last_seen ? new Date(device.last_seen).toLocaleString() : "Never"}
            </TableCell>
            <TableCell>
              <OnlineBadge online={device.online} />
            </TableCell>
            <TableCell>
              <EnrollmentBadge status={device.enrollment_status} />
            </TableCell>
            <TableCell>
              <UpdateNowButton deviceId={device.id} updateRequested={device.update_requested} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
