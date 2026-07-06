"use client";

import {
  LayoutDashboard,
  ScrollText,
  Server,
  Settings,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { usePendingRequests } from "@/lib/pending-requests-context";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/elevation-requests", label: "Elevation Requests", icon: ShieldAlert },
  { href: "/devices", label: "Devices", icon: Server },
  { href: "/audit-logs", label: "Audit Logs", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { pendingCount } = usePendingRequests();

  return (
    <aside className="hidden w-64 shrink-0 border-r bg-background md:flex md:flex-col">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <ShieldCheck className="h-6 w-6 text-primary" />
        <span className="font-semibold tracking-tight">ElevateGate</span>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <span className="flex items-center gap-2">
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
              {item.href === "/elevation-requests" && pendingCount > 0 && (
                <Badge
                  variant={isActive ? "secondary" : "default"}
                  className="h-5 min-w-5 justify-center px-1.5 tabular-nums"
                >
                  {pendingCount}
                </Badge>
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
