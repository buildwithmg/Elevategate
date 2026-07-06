"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api-client";

/**
 * A 401 from any query or mutation means the backend has decided our session is no longer
 * valid (expired/revoked JWT) - redirect to /login. A full reload (not client-side navigation)
 * deliberately resets all in-memory state rather than leaving stale authenticated UI around.
 */
function handleAuthError(error: unknown) {
  if (error instanceof ApiError && error.status === 401 && typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status < 500) return false;
              return failureCount < 2;
            },
            staleTime: 10_000,
          },
        },
        queryCache: new QueryCache({ onError: handleAuthError }),
        mutationCache: new MutationCache({ onError: handleAuthError }),
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
