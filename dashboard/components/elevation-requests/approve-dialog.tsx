"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { ApiError, approveElevationRequest } from "@/lib/api-client";
import type { ElevationRequest } from "@/lib/schemas";

export function ApproveDialog({ request }: { request: ElevationRequest }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => approveElevationRequest(request.id),
    onSuccess: () => {
      toast.success("Request approved", {
        description: `${request.filename} was approved for ${request.device_hostname}.`,
      });
      setOpen(false);
      queryClient.invalidateQueries({ queryKey: ["elevation-request", request.id] });
      queryClient.invalidateQueries({ queryKey: ["elevation-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (error) => {
      toast.error("Could not approve this request", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
      <DialogTrigger
        render={
          <Button className="bg-emerald-600 text-white hover:bg-emerald-700">Approve Once</Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Confirm Approval</DialogTitle>
          <DialogDescription className="pt-2 text-foreground">
            You are approving elevated execution of this exact application file on this device.
            The approval is tied to the displayed SHA-256 hash and will expire in 5 minutes.
          </DialogDescription>
        </DialogHeader>

        <dl className="space-y-2 rounded-md border bg-muted/40 p-4 text-sm">
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-muted-foreground">Application</dt>
            <dd className="text-right font-medium">{request.filename}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-muted-foreground">Publisher</dt>
            <dd className="text-right font-medium">{request.publisher ?? "Unknown"}</dd>
          </div>
          <div className="flex items-baseline justify-between gap-4">
            <dt className="text-muted-foreground">Device</dt>
            <dd className="text-right font-medium">{request.device_hostname}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">SHA-256</dt>
            <dd className="mt-1 break-all rounded bg-background px-2 py-1 font-mono text-xs">
              {request.sha256}
            </dd>
          </div>
        </dl>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            className="bg-emerald-600 text-white hover:bg-emerald-700"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Approving…" : "Confirm Approval"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
