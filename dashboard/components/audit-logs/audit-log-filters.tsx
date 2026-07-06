"use client";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type AuditLogFilterState = {
  actorType: string;
  action: string;
  targetType: string;
};

export function AuditLogFilters({
  value,
  onChange,
}: {
  value: AuditLogFilterState;
  onChange: (next: AuditLogFilterState) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-40 space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Actor type</label>
        <Select
          value={value.actorType}
          onValueChange={(actorType) => onChange({ ...value, actorType: actorType ?? "all" })}
        >
          <SelectTrigger>
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
            <SelectItem value="device">Device</SelectItem>
            <SelectItem value="system">System</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="w-56 space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Action</label>
        <Input
          placeholder="e.g. elevation_request.approved"
          value={value.action}
          onChange={(event) => onChange({ ...value, action: event.target.value })}
        />
      </div>
      <div className="w-48 space-y-1">
        <label className="text-xs font-medium text-muted-foreground">Target type</label>
        <Input
          placeholder="e.g. elevation_request"
          value={value.targetType}
          onChange={(event) => onChange({ ...value, targetType: event.target.value })}
        />
      </div>
    </div>
  );
}
