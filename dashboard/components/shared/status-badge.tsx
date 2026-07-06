import { Badge } from "@/components/ui/badge";
import type { ElevationRequestStatus, SignatureStatus } from "@/lib/schemas";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<ElevationRequestStatus, string> = {
  pending: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800",
  approved: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800",
  denied: "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
  expired: "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700",
  failed: "bg-orange-100 text-orange-900 border-orange-300 dark:bg-orange-950 dark:text-orange-200 dark:border-orange-800",
};

const STATUS_LABELS: Record<ElevationRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  denied: "Denied",
  expired: "Expired",
  failed: "Failed",
};

export function StatusBadge({
  status,
  className,
}: {
  status: ElevationRequestStatus;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn("font-medium", STATUS_STYLES[status], className)}
    >
      {STATUS_LABELS[status]}
    </Badge>
  );
}

const SIGNATURE_STYLES: Record<SignatureStatus, string> = {
  trusted: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-200 dark:border-emerald-800",
  unsigned: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800",
  untrusted: "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
  hash_mismatch: "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
  revoked: "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-200 dark:border-red-800",
  unknown: "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-900 dark:text-slate-300 dark:border-slate-700",
};

const SIGNATURE_LABELS: Record<SignatureStatus, string> = {
  trusted: "Trusted",
  unsigned: "Unsigned",
  untrusted: "Untrusted",
  hash_mismatch: "Hash Mismatch",
  revoked: "Revoked",
  unknown: "Unknown",
};

export function SignatureStatusBadge({
  status,
  className,
}: {
  status: SignatureStatus;
  className?: string;
}) {
  return (
    <Badge variant="outline" className={cn("font-medium", SIGNATURE_STYLES[status], className)}>
      {SIGNATURE_LABELS[status]}
    </Badge>
  );
}
