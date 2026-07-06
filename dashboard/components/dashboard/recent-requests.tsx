"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { StatusBadge } from "@/components/shared/status-badge";
import { listElevationRequests } from "@/lib/api-client";
import { usePendingRequests } from "@/lib/pending-requests-context";
import { cn } from "@/lib/utils";

export function RecentRequests() {
  const router = useRouter();
  const { newRequestIds } = usePendingRequests();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["elevation-requests", "recent"],
    queryFn: () => listElevationRequests({ limit: 8 }),
    refetchInterval: 5000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Elevation Requests</CardTitle>
      </CardHeader>
      <CardContent>
        {isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : "Failed to load requests."}
            onRetry={() => refetch()}
          />
        ) : isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : !data || data.items.length === 0 ? (
          <EmptyState title="No elevation requests yet" description="Submitted requests will appear here." />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Status</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Application</TableHead>
                <TableHead>Requested</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((item) => {
                const isNew = newRequestIds.has(item.request_uuid);
                return (
                  <TableRow
                    key={item.id}
                    onClick={() => router.push(`/elevation-requests/${item.id}`)}
                    className={cn(
                      "cursor-pointer",
                      isNew && "animate-pulse bg-amber-50 dark:bg-amber-950/40",
                    )}
                  >
                    <TableCell>
                      <StatusBadge status={item.status} />
                    </TableCell>
                    <TableCell>{item.username}</TableCell>
                    <TableCell>{item.filename}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(item.requested_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
