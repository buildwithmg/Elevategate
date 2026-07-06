"use client";

import { useState } from "react";

import { RequestsTable } from "@/components/elevation-requests/requests-table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ElevationRequestStatus } from "@/lib/schemas";

const FILTERS: { value: ElevationRequestStatus | "all"; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "denied", label: "Denied" },
  { value: "expired", label: "Expired" },
  { value: "all", label: "All" },
];

export default function ElevationRequestsPage() {
  const [filter, setFilter] = useState<ElevationRequestStatus | "all">("pending");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Elevation Requests</h1>
        <p className="text-sm text-muted-foreground">
          Review requests submitted by enrolled devices.
        </p>
      </div>

      <Tabs value={filter} onValueChange={(value) => setFilter(value as ElevationRequestStatus | "all")}>
        <TabsList>
          {FILTERS.map((item) => (
            <TabsTrigger key={item.value} value={item.value}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <RequestsTable statusFilter={filter} />
    </div>
  );
}
