"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, HardDrive, MemoryStick, WifiOff } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getDashboardAlerts } from "@/lib/api-client";
import type { Alert as AlertItem } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const ICONS = {
  low_disk_space: HardDrive,
  high_ram_usage: MemoryStick,
  device_offline: WifiOff,
} as const;

const TITLES = {
  low_disk_space: "Low disk space",
  high_ram_usage: "High RAM usage",
  device_offline: "Device offline",
} as const;

function AlertRow({ alert }: { alert: AlertItem }) {
  const Icon = ICONS[alert.type] ?? AlertTriangle;
  const isCritical = alert.severity === "critical";
  return (
    <Alert
      variant={isCritical ? "destructive" : "default"}
      className={cn(!isCritical && "border-amber-300 dark:border-amber-800")}
    >
      <Icon />
      <AlertTitle>
        {TITLES[alert.type]} — {alert.hostname}
      </AlertTitle>
      <AlertDescription>{alert.message}</AlertDescription>
    </Alert>
  );
}

export function AlertsBanner() {
  const { data } = useQuery({
    queryKey: ["dashboard-alerts"],
    queryFn: getDashboardAlerts,
    refetchInterval: 30000,
  });

  if (!data || data.items.length === 0) return null;

  return (
    <div className="space-y-2">
      {data.items.map((alert, index) => (
        <AlertRow key={`${alert.device_id}-${alert.type}-${index}`} alert={alert} />
      ))}
    </div>
  );
}
