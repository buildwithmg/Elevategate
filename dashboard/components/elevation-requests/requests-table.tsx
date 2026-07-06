"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

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
import { SignatureStatusBadge, StatusBadge } from "@/components/shared/status-badge";
import { listElevationRequests } from "@/lib/api-client";
import { usePendingRequests } from "@/lib/pending-requests-context";
import type { ElevationRequestStatus } from "@/lib/schemas";
import { cn } from "@/lib/utils";

export function RequestsTable({ statusFilter }: { statusFilter: ElevationRequestStatus | "all" }) {
  const router = useRouter();
  const { newRequestIds } = usePendingRequests();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["elevation-requests", "list", statusFilter],
    queryFn: () =>
      listElevationRequests({
        status: statusFilter === "all" ? undefined : statusFilter,
        limit: 100,
      }),
    refetchInterval: statusFilter === "pending" || statusFilter === "all" ? 5000 : undefined,
  });

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load elevation requests."}
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        title="No matching elevation requests"
        description="Requests submitted by enrolled devices will show up here."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>User</TableHead>
          <TableHead>Device</TableHead>
          <TableHead>Application</TableHead>
          <TableHead>Publisher</TableHead>
          <TableHead>Signature</TableHead>
          <TableHead>Requested</TableHead>
          <TableHead>Reason</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((item) => {
          const isPending = item.status === "pending";
          const isNew = newRequestIds.has(item.request_uuid);
          return (
            <TableRow
              key={item.id}
              onClick={() => router.push(`/elevation-requests/${item.id}`)}
              className={cn(
                "cursor-pointer",
                // Pending requests are the actionable queue - keep them visually prominent
                // wherever they appear, not just under the Pending filter.
                isPending && "bg-amber-50/70 font-medium dark:bg-amber-950/30",
                isNew && "animate-pulse bg-amber-100 dark:bg-amber-900/50",
              )}
            >
              <TableCell>
                <StatusBadge status={item.status} />
              </TableCell>
              <TableCell>{item.username ?? "—"}</TableCell>
              <TableCell>{item.device_hostname}</TableCell>
              <TableCell className="max-w-48 truncate" title={item.filename}>
                {item.filename}
              </TableCell>
              <TableCell className="max-w-40 truncate" title={item.publisher ?? undefined}>
                {item.publisher ?? <span className="text-muted-foreground">—</span>}
              </TableCell>
              <TableCell>
                <SignatureStatusBadge status={item.signature_status} />
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">
                {new Date(item.requested_at).toLocaleString()}
              </TableCell>
              <TableCell className="max-w-56 truncate" title={item.reason}>
                {item.reason}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
