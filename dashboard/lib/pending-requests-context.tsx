"use client";

import { useQuery } from "@tanstack/react-query";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { toast } from "sonner";

import { listElevationRequests } from "@/lib/api-client";
import type { ElevationRequest } from "@/lib/schemas";

const POLL_INTERVAL_MS = 5000;
/** How long a request stays visually flagged as "new" after first appearing. */
const HIGHLIGHT_DURATION_MS = 12_000;

type PendingRequestsContextValue = {
  pendingRequests: ElevationRequest[];
  pendingCount: number;
  isLoading: boolean;
  /** request_uuids that appeared in the most recent polling cycles, for row highlighting. */
  newRequestIds: ReadonlySet<string>;
};

const PendingRequestsContext = createContext<PendingRequestsContextValue | null>(null);

/**
 * Polls GET /elevation-requests?status=pending every 5s (TanStack Query's refetchInterval) and
 * diffs the result against what it saw last time. Mounted exactly once (in the dashboard layout)
 * so the "new request" toast never fires more than once per request, regardless of how many
 * components read the resulting counts/highlight set via usePendingRequests().
 */
export function PendingRequestsProvider({ children }: { children: ReactNode }) {
  const seenIdsRef = useRef<Set<string> | null>(null);
  const [newRequestIds, setNewRequestIds] = useState<Set<string>>(new Set());

  const query = useQuery({
    queryKey: ["elevation-requests", "pending-poll"],
    queryFn: () => listElevationRequests({ status: "pending", limit: 100 }),
    refetchInterval: POLL_INTERVAL_MS,
    // This is the one query where a background tab shouldn't stop polling: the whole point of
    // the "new request" toast is to notice something while the admin is looking at something
    // else. TanStack Query defaults to pausing refetchInterval for hidden tabs, which is the
    // right call for the rest of the app's queries but wrong for this one specifically.
    refetchIntervalInBackground: true,
  });

  useEffect(() => {
    if (!query.data) return;
    const currentIds = new Set(query.data.items.map((item) => item.request_uuid));

    if (seenIdsRef.current === null) {
      // First load after mount: these are pre-existing requests, not "new arrivals" - don't toast.
      seenIdsRef.current = currentIds;
      return;
    }

    const previouslySeen = seenIdsRef.current;
    const freshlyArrived = query.data.items.filter(
      (item) => !previouslySeen.has(item.request_uuid),
    );
    seenIdsRef.current = currentIds;

    if (freshlyArrived.length === 0) return;

    for (const item of freshlyArrived) {
      toast.info("New elevation request", {
        description: `${item.username ?? "Someone"} wants to run ${item.filename} on device #${item.device_id}.`,
      });
    }

    setNewRequestIds((prev) => {
      const next = new Set(prev);
      freshlyArrived.forEach((item) => next.add(item.request_uuid));
      return next;
    });

    const timeout = setTimeout(() => {
      setNewRequestIds((prev) => {
        const next = new Set(prev);
        freshlyArrived.forEach((item) => next.delete(item.request_uuid));
        return next;
      });
    }, HIGHLIGHT_DURATION_MS);

    return () => clearTimeout(timeout);
  }, [query.data]);

  const value: PendingRequestsContextValue = {
    pendingRequests: query.data?.items ?? [],
    pendingCount: query.data?.total ?? 0,
    isLoading: query.isLoading,
    newRequestIds,
  };

  return (
    <PendingRequestsContext.Provider value={value}>{children}</PendingRequestsContext.Provider>
  );
}

export function usePendingRequests(): PendingRequestsContextValue {
  const context = useContext(PendingRequestsContext);
  if (!context) {
    throw new Error("usePendingRequests must be used within a PendingRequestsProvider.");
  }
  return context;
}
