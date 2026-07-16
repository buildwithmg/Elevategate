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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createDeviceGroup } from "@/lib/api-client";

export function CreateGroupDialog() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => createDeviceGroup(name.trim(), description.trim() || undefined),
    onSuccess: () => {
      toast.success("Group created", { description: `"${name.trim()}" is ready to assign devices to.` });
      setOpen(false);
      setName("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["device-groups"] });
    },
    onError: (error) => {
      toast.error("Could not create group", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
      <DialogTrigger render={<Button>New group</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New device group</DialogTitle>
          <DialogDescription>
            Groups devices together for app-allowlist scoping and organization.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="group-name">Name</Label>
            <Input
              id="group-name"
              placeholder="e.g. Finance"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={mutation.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="group-description">Description (optional)</Label>
            <Textarea
              id="group-description"
              placeholder="What this group is for…"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={mutation.isPending}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={mutation.isPending}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !name.trim()}
          >
            {mutation.isPending ? "Creating…" : "Create group"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
