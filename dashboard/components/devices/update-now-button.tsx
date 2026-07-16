"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, requestDeviceUpdate } from "@/lib/api-client";

export function UpdateNowButton({ deviceId, updateRequested }: { deviceId: number; updateRequested: boolean }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => requestDeviceUpdate(deviceId),
    onSuccess: () => {
      toast.success("Update requested", {
        description: "The agent will check for and apply an update on its next check-in.",
      });
      queryClient.invalidateQueries({ queryKey: ["devices"] });
    },
    onError: (error) => {
      toast.error("Could not request an update", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  if (updateRequested) {
    return (
      <Button variant="outline" size="sm" disabled>
        Update pending…
      </Button>
    );
  }

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      {mutation.isPending ? "Requesting…" : "Update now"}
    </Button>
  );
}
