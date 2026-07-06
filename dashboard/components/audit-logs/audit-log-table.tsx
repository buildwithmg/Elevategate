"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  AuditLogFilters,
  type AuditLogFilterState,
} from "@/components/audit-logs/audit-log-filters";
import { EmptyState, ErrorState } from "@/components/shared/state-views";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { listAuditLogs } from "@/lib/api-client";
import type { AuditLog } from "@/lib/schemas";

const PAGE_SIZE = 25;

function describeActor(log: AuditLog): string {
  switch (log.actor_type) {
    case "admin":
      return `Admin #${log.actor_id}`;
    case "device":
      return `Device ${log.actor_id.slice(0, 8)}…`;
    case "system":
      return "System";
    default:
      return log.actor_id;
  }
}

export function AuditLogTable() {
  const [filters, setFilters] = useState<AuditLogFilterState>({
    actorType: "all",
    action: "",
    targetType: "",
  });
  const [page, setPage] = useState(0);

  function updateFilters(next: AuditLogFilterState) {
    setFilters(next);
    setPage(0);
  }

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["audit-logs", filters, page],
    queryFn: () =>
      listAuditLogs({
        actor_type: filters.actorType === "all" ? undefined : filters.actorType,
        action: filters.action.trim() || undefined,
        target_type: filters.targetType.trim() || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });

  const total = data?.total ?? 0;
  const rangeStart = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = Math.min(total, (page + 1) * PAGE_SIZE);

  return (
    <div className="space-y-4">
      <AuditLogFilters value={filters} onChange={updateFilters} />

      {isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load audit logs."}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState title="No matching audit log entries" description="Try adjusting the filters above." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Metadata</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {new Date(log.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-2">
                      <Badge variant="outline" className="capitalize">
                        {log.actor_type}
                      </Badge>
                      {describeActor(log)}
                    </span>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{log.action}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {log.target_type} #{log.target_id}
                  </TableCell>
                  <TableCell className="max-w-72 truncate font-mono text-xs text-muted-foreground">
                    {log.metadata ? JSON.stringify(log.metadata) : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {rangeStart}–{rangeEnd} of {total}
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 0}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={rangeEnd >= total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
