"use client";

import { useQuery } from "@tanstack/react-query";
import { Copy, Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/state-views";
import { getEnrollmentInfo } from "@/lib/api-client";

async function copyToClipboard(value: string, label: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copied to clipboard`);
  } catch {
    toast.error(`Could not copy ${label.toLowerCase()}`);
  }
}

export function EnrollmentCard() {
  const [revealed, setRevealed] = useState(false);
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["enrollment-info"],
    queryFn: getEnrollmentInfo,
  });

  return (
    <Card className="max-w-lg">
      <CardHeader>
        <CardTitle>Agent installation</CardTitle>
        <CardDescription>
          Enrollment key and one-line install command for adding a new Windows machine.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isError ? (
          <ErrorState
            message={error instanceof Error ? error.message : "Failed to load enrollment info."}
            onRetry={() => refetch()}
          />
        ) : isLoading || !data ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">Enrollment key</label>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate rounded-md border bg-muted px-2.5 py-1.5 font-mono text-xs">
                  {revealed ? data.enrollment_key : "•".repeat(24)}
                </code>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setRevealed((prev) => !prev)}
                  title={revealed ? "Hide" : "Reveal"}
                >
                  {revealed ? <EyeOff /> : <Eye />}
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => copyToClipboard(data.enrollment_key, "Enrollment key")}
                  title="Copy"
                >
                  <Copy />
                </Button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Quick install (run in PowerShell on the target machine)
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 overflow-x-auto text-nowrap rounded-md border bg-muted px-2.5 py-1.5 font-mono text-xs">
                  {data.install_command}
                </code>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => copyToClipboard(data.install_command, "Install command")}
                  title="Copy"
                >
                  <Copy />
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                You&rsquo;ll be prompted once for the enrollment key above.
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
