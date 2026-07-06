"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { ApproveDialog } from "@/components/elevation-requests/approve-dialog";
import { DenyDialog } from "@/components/elevation-requests/deny-dialog";
import { ErrorState } from "@/components/shared/state-views";
import { SignatureStatusBadge, StatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getElevationRequest } from "@/lib/api-client";

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-1 gap-1 border-b py-3 last:border-0 sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className={`text-sm break-all sm:col-span-2 ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

export function ElevationRequestDetail({ id }: { id: number }) {
  const router = useRouter();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["elevation-request", id],
    queryFn: () => getElevationRequest(id),
    refetchInterval: 5000,
  });

  return (
    <div className="space-y-4">
      <Button
        variant="ghost"
        size="sm"
        className="-ml-2 gap-1"
        onClick={() => router.push("/elevation-requests")}
      >
        <ArrowLeft className="h-4 w-4" /> Back to Elevation Requests
      </Button>

      {isError ? (
        <ErrorState
          message={error instanceof Error ? error.message : "Failed to load this request."}
          onRetry={() => refetch()}
        />
      ) : isLoading || !data ? (
        <Skeleton className="h-[32rem] w-full" />
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-xl">{data.filename}</CardTitle>
              <p className="text-sm text-muted-foreground">Request #{data.id}</p>
            </div>
            <StatusBadge status={data.status} className="shrink-0 text-sm" />
          </CardHeader>
          <CardContent className="space-y-6">
            <dl>
              <DetailRow label="User" value={data.username} />
              <DetailRow label="Device" value={data.device_uuid} mono />
              <DetailRow label="Hostname" value={data.device_hostname} />
              <DetailRow label="Application filename" value={data.filename} />
              <DetailRow label="Full canonical path" value={data.canonical_path} mono />
              <DetailRow label="SHA-256" value={data.sha256} mono />
              <DetailRow label="Publisher" value={data.publisher ?? "Unknown"} />
              <DetailRow
                label="Digital signature status"
                value={<SignatureStatusBadge status={data.signature_status} />}
              />
              <DetailRow label="File size" value={formatBytes(data.file_size)} />
              <DetailRow label="File version" value={data.file_version ?? "—"} />
              <DetailRow label="Reason" value={data.reason} />
              <DetailRow label="Requested" value={new Date(data.requested_at).toLocaleString()} />
              {data.reviewed_at && (
                <DetailRow label="Reviewed" value={new Date(data.reviewed_at).toLocaleString()} />
              )}
              <DetailRow label="Review window expires" value={new Date(data.expires_at).toLocaleString()} />
            </dl>

            {data.status === "pending" ? (
              <div className="flex flex-wrap gap-3 border-t pt-6">
                <ApproveDialog request={data} />
                <DenyDialog request={data} />
              </div>
            ) : (
              <p className="border-t pt-6 text-sm text-muted-foreground">
                This request has already been decided and can no longer be acted on.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
