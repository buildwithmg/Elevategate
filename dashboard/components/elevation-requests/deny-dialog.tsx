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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, denyElevationRequest } from "@/lib/api-client";
import type { ElevationRequest } from "@/lib/schemas";

export function DenyDialog({ request }: { request: ElevationRequest }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => denyElevationRequest(request.id, note.trim() || undefined),
    onSuccess: () => {
      toast.success("Request denied", {
        description: `${request.filename} was denied for ${request.device_hostname}.`,
      });
      setOpen(false);
      setNote("");
      queryClient.invalidateQueries({ queryKey: ["elevation-request", request.id] });
      queryClient.invalidateQueries({ queryKey: ["elevation-requests"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] });
    },
    onError: (error) => {
      toast.error("Could not deny this request", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
      <DialogTrigger render={<Button variant="destructive">Deny</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Confirm Denial</DialogTitle>
          <DialogDescription>
            {request.username ?? "This user"} will not be able to run {request.filename} on{" "}
            {request.device_hostname} with this request.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="deny-note">Note (optional)</Label>
          <Textarea
            id="deny-note"
            placeholder="Reason for denial, visible only in the audit log…"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            disabled={mutation.isPending}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Denying…" : "Confirm Denial"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
