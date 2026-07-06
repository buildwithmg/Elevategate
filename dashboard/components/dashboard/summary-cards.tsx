"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Server, ServerOff, XCircle } from "lucide-react";
import type { ComponentType } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/state-views";
import { getDashboardSummary } from "@/lib/api-client";
import type { DashboardSummary } from "@/lib/schemas";

const CARD_DEFS: {
  key: keyof DashboardSummary;
  label: string;
  icon: ComponentType<{ className?: string }>;
  accent: string;
}[] = [
  { key: "pending_requests", label: "Pending Requests", icon: Clock, accent: "text-amber-600" },
  { key: "approved_today", label: "Approved Today", icon: CheckCircle2, accent: "text-emerald-600" },
  { key: "denied_today", label: "Denied Today", icon: XCircle, accent: "text-red-600" },
  { key: "active_devices", label: "Active Devices", icon: Server, accent: "text-emerald-600" },
  { key: "offline_devices", label: "Offline Devices", icon: ServerOff, accent: "text-slate-500" },
];

export function SummaryCards() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
    // Kept live at the same 5s cadence as the pending-requests poll so every number on this
    // page - not just the count in the sidebar - reflects reality within a few seconds.
    refetchInterval: 5000,
  });

  if (isError) {
    return (
      <ErrorState
        message={error instanceof Error ? error.message : "Failed to load the dashboard summary."}
        onRetry={() => refetch()}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {CARD_DEFS.map((def) => {
        const Icon = def.icon;
        return (
          <Card key={def.key}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {def.label}
              </CardTitle>
              <Icon className={`h-4 w-4 ${def.accent}`} />
            </CardHeader>
            <CardContent>
              {isLoading || !data ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-2xl font-bold tabular-nums">{data[def.key]}</p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
