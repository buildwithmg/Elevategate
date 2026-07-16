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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, createAppAllowlistEntry, listDeviceGroups } from "@/lib/api-client";

const GLOBAL = "global";

export function CreateEntryDialog() {
  const [open, setOpen] = useState(false);
  const [publisher, setPublisher] = useState("");
  const [filename, setFilename] = useState("");
  const [description, setDescription] = useState("");
  const [groupId, setGroupId] = useState<string>(GLOBAL);
  const queryClient = useQueryClient();

  const { data: groups } = useQuery({ queryKey: ["device-groups"], queryFn: listDeviceGroups });

  const mutation = useMutation({
    mutationFn: () =>
      createAppAllowlistEntry({
        publisher: publisher.trim(),
        filename: filename.trim(),
        description: description.trim() || undefined,
        group_id: groupId === GLOBAL ? null : Number(groupId),
      }),
    onSuccess: () => {
      toast.success("Allowlist entry created", {
        description: `${filename.trim()} from ${publisher.trim()} will now auto-approve.`,
      });
      setOpen(false);
      setPublisher("");
      setFilename("");
      setDescription("");
      setGroupId(GLOBAL);
      queryClient.invalidateQueries({ queryKey: ["app-allowlist"] });
    },
    onError: (error) => {
      toast.error("Could not create allowlist entry", {
        description: error instanceof ApiError ? error.message : "An unexpected error occurred.",
      });
    },
  });

  return (
    <Dialog open={open} onOpenChange={(next) => !mutation.isPending && setOpen(next)}>
      <DialogTrigger render={<Button>New allowlist entry</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New app allowlist entry</DialogTitle>
          <DialogDescription>
            Matching requests auto-approve without a human decision — but only when the submitted
            file&rsquo;s signature is independently verified Trusted. Everything else still goes
            to the normal review queue.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="entry-publisher">Publisher (signed common name)</Label>
            <Input
              id="entry-publisher"
              placeholder="e.g. Contoso Ltd."
              value={publisher}
              onChange={(event) => setPublisher(event.target.value)}
              disabled={mutation.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="entry-filename">Filename</Label>
            <Input
              id="entry-filename"
              placeholder="e.g. ContosoSetup.exe"
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
              disabled={mutation.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label>Applies to</Label>
            <Select value={groupId} onValueChange={(value) => setGroupId(value ?? GLOBAL)}>
              <SelectTrigger>
                {/* Base UI's Select.Value doesn't auto-derive a label from mounted SelectItems
                    for dynamically-loaded items - resolve it ourselves. */}
                <SelectValue placeholder="All devices">
                  {(value: string | null) => {
                    if (!value || value === GLOBAL) return "All devices";
                    const group = groups?.items.find((g) => String(g.id) === value);
                    return group ? `${group.name} only` : "All devices";
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={GLOBAL}>All devices</SelectItem>
                {(groups?.items ?? []).map((group) => (
                  <SelectItem key={group.id} value={String(group.id)}>
                    {group.name} only
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="entry-description">Description (optional)</Label>
            <Textarea
              id="entry-description"
              placeholder="Why this app is allowed…"
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
            disabled={mutation.isPending || !publisher.trim() || !filename.trim()}
          >
            {mutation.isPending ? "Creating…" : "Create entry"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
