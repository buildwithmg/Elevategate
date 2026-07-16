import { z } from "zod";

/**
 * Every shape here mirrors the ElevateGate FastAPI backend's actual response bodies
 * (see docs/API_CONTRACT.md at the repo root) - field names are snake_case on purpose, matching
 * the wire format exactly rather than being remapped to camelCase, so there's no silent
 * translation layer to get out of sync with the backend.
 */

export const AdminRoleSchema = z.enum(["admin", "reviewer"]);
export type AdminRole = z.infer<typeof AdminRoleSchema>;

export const MeResponseSchema = z.object({
  id: z.number(),
  email: z.string(),
  name: z.string(),
  role: AdminRoleSchema,
  is_active: z.boolean(),
  created_at: z.string(),
});
export type MeResponse = z.infer<typeof MeResponseSchema>;

// "failed" is included for forward-compatibility with the UI's status-indicator spec, but the
// backend's ElevationRequestStatus enum today only ever produces the other four - it's an
// agent-local concept that has never reached the backend. See dashboard/README.md.
export const ElevationRequestStatusSchema = z.enum([
  "pending",
  "approved",
  "denied",
  "expired",
  "failed",
]);
export type ElevationRequestStatus = z.infer<typeof ElevationRequestStatusSchema>;

export const SignatureStatusSchema = z.enum([
  "unsigned",
  "trusted",
  "untrusted",
  "hash_mismatch",
  "revoked",
  "unknown",
]);
export type SignatureStatus = z.infer<typeof SignatureStatusSchema>;

export const ElevationRequestSchema = z.object({
  id: z.number(),
  request_uuid: z.string(),
  device_id: z.number(),
  device_uuid: z.string(),
  device_hostname: z.string(),
  // Null when submitted by the .NET agent, which never captures a Windows username.
  username: z.string().nullable(),
  filename: z.string(),
  canonical_path: z.string(),
  sha256: z.string(),
  publisher: z.string().nullable(),
  signature_status: SignatureStatusSchema,
  file_size: z.number(),
  file_version: z.string().nullable(),
  reason: z.string(),
  status: ElevationRequestStatusSchema,
  requested_at: z.string(),
  reviewed_at: z.string().nullable(),
  reviewed_by: z.number().nullable(),
  expires_at: z.string(),
});
export type ElevationRequest = z.infer<typeof ElevationRequestSchema>;

export const ElevationRequestListSchema = z.object({
  items: z.array(ElevationRequestSchema),
  total: z.number(),
});
export type ElevationRequestList = z.infer<typeof ElevationRequestListSchema>;

export const EnrollmentStatusSchema = z.enum(["active", "revoked"]);
export type EnrollmentStatus = z.infer<typeof EnrollmentStatusSchema>;

export const DeviceSchema = z.object({
  id: z.number(),
  device_uuid: z.string(),
  hostname: z.string(),
  operating_system: z.string(),
  agent_version: z.string().nullable(),
  last_seen: z.string().nullable(),
  enrollment_status: EnrollmentStatusSchema,
  online: z.boolean(),
  created_at: z.string(),
  group_id: z.number().nullable(),
  group_name: z.string().nullable(),
  disk_total_bytes: z.number().nullable(),
  disk_free_bytes: z.number().nullable(),
  ram_total_bytes: z.number().nullable(),
  ram_used_bytes: z.number().nullable(),
  last_telemetry_at: z.string().nullable(),
  update_requested: z.boolean(),
});
export type Device = z.infer<typeof DeviceSchema>;

export const DeviceListSchema = z.object({
  items: z.array(DeviceSchema),
  total: z.number(),
});
export type DeviceList = z.infer<typeof DeviceListSchema>;

export const DeviceGroupSchema = z.object({
  id: z.number(),
  name: z.string(),
  description: z.string().nullable(),
  device_count: z.number(),
  created_at: z.string(),
});
export type DeviceGroup = z.infer<typeof DeviceGroupSchema>;

export const DeviceGroupListSchema = z.object({
  items: z.array(DeviceGroupSchema),
  total: z.number(),
});
export type DeviceGroupList = z.infer<typeof DeviceGroupListSchema>;

export const AppAllowlistEntrySchema = z.object({
  id: z.number(),
  group_id: z.number().nullable(),
  group_name: z.string().nullable(),
  publisher: z.string(),
  filename: z.string(),
  description: z.string().nullable(),
  created_by: z.number().nullable(),
  created_at: z.string(),
});
export type AppAllowlistEntry = z.infer<typeof AppAllowlistEntrySchema>;

export const AppAllowlistEntryListSchema = z.object({
  items: z.array(AppAllowlistEntrySchema),
  total: z.number(),
});
export type AppAllowlistEntryList = z.infer<typeof AppAllowlistEntryListSchema>;

export const AlertSeveritySchema = z.enum(["critical", "warning"]);
export type AlertSeverity = z.infer<typeof AlertSeveritySchema>;

export const AlertTypeSchema = z.enum(["low_disk_space", "high_ram_usage", "device_offline"]);
export type AlertType = z.infer<typeof AlertTypeSchema>;

export const AlertSchema = z.object({
  severity: AlertSeveritySchema,
  type: AlertTypeSchema,
  device_id: z.number(),
  device_uuid: z.string(),
  hostname: z.string(),
  message: z.string(),
});
export type Alert = z.infer<typeof AlertSchema>;

export const AlertListSchema = z.object({
  items: z.array(AlertSchema),
  total: z.number(),
});
export type AlertList = z.infer<typeof AlertListSchema>;

export const EnrollmentInfoSchema = z.object({
  enrollment_key: z.string(),
  install_command: z.string(),
});
export type EnrollmentInfo = z.infer<typeof EnrollmentInfoSchema>;

export const ActorTypeSchema = z.enum(["admin", "device", "system"]);
export type ActorType = z.infer<typeof ActorTypeSchema>;

export const AuditLogSchema = z.object({
  id: z.number(),
  actor_type: ActorTypeSchema,
  actor_id: z.string(),
  action: z.string(),
  target_type: z.string(),
  target_id: z.string(),
  metadata: z.record(z.string(), z.unknown()).nullable(),
  timestamp: z.string(),
});
export type AuditLog = z.infer<typeof AuditLogSchema>;

export const AuditLogListSchema = z.object({
  items: z.array(AuditLogSchema),
  total: z.number(),
});
export type AuditLogList = z.infer<typeof AuditLogListSchema>;

export const DashboardSummarySchema = z.object({
  pending_requests: z.number(),
  approved_today: z.number(),
  denied_today: z.number(),
  active_devices: z.number(),
  offline_devices: z.number(),
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

/** FastAPI's error body shape: `{"detail": "message"}` or `{"detail": [{"loc", "msg", "type"}, ...]}` for 422s. */
export const ErrorBodySchema = z.object({
  detail: z.union([z.string(), z.array(z.object({ msg: z.string() }))]),
});

export function extractErrorMessage(body: unknown, fallback: string): string {
  const parsed = ErrorBodySchema.safeParse(body);
  if (!parsed.success) return fallback;
  if (typeof parsed.data.detail === "string") return parsed.data.detail;
  return parsed.data.detail.map((issue) => issue.msg).join(" ");
}
