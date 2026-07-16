"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, assignDeviceGroup, listDeviceGroups } from "@/lib/api-client";

const UNASSIGNED = "unassigned";

export function DeviceGroupSelect({ deviceId, groupId }: { deviceId: number; groupId: number | null }) {
  const queryClient = useQueryClient();
  const { data: groups } = useQuery({
    queryKey: ["device-groups"],
    queryFn: listDeviceGroups,
  });

  const mutation = useMutation({
    mutationFn: (nextGroupId: number | null) => assignDeviceGroup(deviceId, nextGroupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    },
    onError: (error) => {
      toast.error("Could not update this device's group", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Select
      value={groupId === null ? UNASSIGNED : String(groupId)}
      onValueChange={(value) =>
        mutation.mutate(value === UNASSIGNED ? null : Number(value))
      }
    >
      <SelectTrigger className="h-8 w-40 text-xs">
        {/* Base UI's Select.Value doesn't auto-derive a label from mounted SelectItems - it
            needs either a render-prop or an `items` map on the root. Since the group list loads
            asynchronously, resolve the label ourselves rather than showing the raw id/value. */}
        <SelectValue placeholder="Unassigned">
          {(value: string | null) => {
            if (!value || value === UNASSIGNED) return "Unassigned";
            return groups?.items.find((group) => String(group.id) === value)?.name ?? "Unassigned";
          }}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
        {(groups?.items ?? []).map((group) => (
          <SelectItem key={group.id} value={String(group.id)}>
            {group.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
