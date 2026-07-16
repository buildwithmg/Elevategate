"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { ApiError, deleteDeviceGroup, listDeviceGroups } from "@/lib/api-client";
import type { DeviceGroup } from "@/lib/schemas";

function DeleteGroupDialog({ group }: { group: DeviceGroup }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => deleteDeviceGroup(group.id),
    onSuccess: () => {
      toast.success("Group deleted", {
        description:
          group.device_count > 0
            ? `${group.device_count} device(s) were unassigned.`
            : `"${group.name}" was deleted.`,
      });
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["device-groups"] });
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      queryClient.invalidateQueries({ queryKey: ["app-allowlist"] });
    },
    onError: (error) => {
      toast.error("Could not delete this group", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
      <DialogTrigger render={<Button variant="destructive" size="sm">Delete</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Delete &ldquo;{group.name}&rdquo;?</DialogTitle>
          <DialogDescription>
            {group.device_count > 0
              ? `${group.device_count} device(s) currently in this group will become unassigned.`
              : "This group has no devices assigned."}{" "}
            Any app-allowlist entries scoped to this group will also be deleted.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? "Deleting…" : "Delete group"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function GroupsTable() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["device-groups"],
    queryFn: listDeviceGroups,
  });

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load device groups."}
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
        title="No device groups yet"
        description="Create a group to organize devices and scope app-allowlist entries."
      />
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Description</TableHead>
          <TableHead>Devices</TableHead>
          <TableHead>Created</TableHead>
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((group) => (
          <TableRow key={group.id}>
            <TableCell className="font-medium">{group.name}</TableCell>
            <TableCell className="text-muted-foreground">{group.description ?? "—"}</TableCell>
            <TableCell>{group.device_count}</TableCell>
            <TableCell className="text-muted-foreground">
              {new Date(group.created_at).toLocaleDateString()}
            </TableCell>
            <TableCell className="text-right">
              <DeleteGroupDialog group={group} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
