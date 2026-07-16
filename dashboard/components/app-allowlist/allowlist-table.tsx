"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

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
import { EmptyState, ErrorState } from "@/components/shared/state-views";
import { ApiError, deleteAppAllowlistEntry, listAppAllowlistEntries } from "@/lib/api-client";

export function AllowlistTable() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["app-allowlist"],
    queryFn: () => listAppAllowlistEntries(),
  });

  const deleteMutation = useMutation({
    mutationFn: (entryId: number) => deleteAppAllowlistEntry(entryId),
    onSuccess: () => {
      toast.success("Allowlist entry deleted");
      queryClient.invalidateQueries({ queryKey: ["app-allowlist"] });
    },
    onError: (mutationError) => {
      toast.error("Could not delete this entry", {
        description:
          mutationError instanceof ApiError ? mutationError.message : "An unexpected error occurred.",
      });
    },
  });

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load the app allowlist."}
        onRetry={() => refetch()}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <EmptyState
        title="No allowlist entries yet"
        description="Apps you add here will auto-approve for matching devices without a human decision."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Publisher</TableHead>
          <TableHead>Filename</TableHead>
          <TableHead>Applies to</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell className="font-medium">{entry.publisher}</TableCell>
            <TableCell className="font-mono text-xs">{entry.filename}</TableCell>
            <TableCell>
              {entry.group_name ? (
                <Badge variant="outline">{entry.group_name}</Badge>
              ) : (
                <Badge variant="secondary">All devices</Badge>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">{entry.description ?? "—"}</TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(entry.created_at).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-right">
              <Button
                variant="destructive"
                size="sm"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate(entry.id)}
              >
                Delete
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
