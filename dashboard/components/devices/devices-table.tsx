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
import { listDevices } from "@/lib/api-client";
import { cn } from "@/lib/utils";

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
          <TableHead>Last Seen</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Enrollment</TableHead>
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
            <TableCell>{device.agent_version}</TableCell>
            <TableCell className="text-muted-foreground">
              {device.last_seen ? new Date(device.last_seen).toLocaleString() : "Never"}
            </TableCell>
            <TableCell>
              <OnlineBadge online={device.online} />
            </TableCell>
            <TableCell>
              <EnrollmentBadge status={device.enrollment_status} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
