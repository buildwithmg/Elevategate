import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatBytesGB(bytes: number): string {
  return `${(bytes / 1024 ** 3).toFixed(1)} GB`
}

/** Percentage of a whole used up, e.g. formatUsagePercent(used, total) for RAM/disk usage. */
export function formatUsagePercent(used: number, total: number): string {
  if (total <= 0) return "—"
  return `${Math.round((used / total) * 100)}%`
}
