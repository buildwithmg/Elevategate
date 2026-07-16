import {
  AlertListSchema,
  type AlertList,
  AppAllowlistEntryListSchema,
  AppAllowlistEntrySchema,
  type AppAllowlistEntry,
  type AppAllowlistEntryList,
  AuditLogListSchema,
  type AuditLogList,
  DashboardSummarySchema,
  type DashboardSummary,
  DeviceGroupListSchema,
  DeviceGroupSchema,
  type DeviceGroup,
  type DeviceGroupList,
  DeviceListSchema,
  DeviceSchema,
  type Device,
  type DeviceList,
  ElevationRequestListSchema,
  ElevationRequestSchema,
  type ElevationRequest,
  type ElevationRequestList,
  EnrollmentInfoSchema,
  type EnrollmentInfo,
  MeResponseSchema,
  type MeResponse,
  extractErrorMessage,
} from "@/lib/schemas";
import { z } from "zod";

/** Thrown by every api-client function on a non-2xx response or a response that fails Zod validation. */
export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });

  const body = await readBody(response);

  if (!response.ok) {
    throw new ApiError(
      response.status,
      extractErrorMessage(body, `Request failed with status ${response.status}.`),
    );
  }

  const parsed = schema.safeParse(body);
  if (!parsed.success) {
    console.error(`Response from /${path} did not match the expected shape:`, parsed.error);
    throw new ApiError(response.status, "The server returned an unexpected response shape.");
  }

  return parsed.data;
}

export function getMe(): Promise<MeResponse> {
  return request("auth/me", MeResponseSchema);
}

export function getDashboardSummary(): Promise<DashboardSummary> {
  return request("dashboard/summary", DashboardSummarySchema);
}

export type ElevationRequestListParams = {
  status?: string;
  limit?: number;
  offset?: number;
};

export function listElevationRequests(
  params: ElevationRequestListParams = {},
): Promise<ElevationRequestList> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const query = search.toString();
  return request(`elevation-requests${query ? `?${query}` : ""}`, ElevationRequestListSchema);
}

export function getElevationRequest(id: number): Promise<ElevationRequest> {
  return request(`elevation-requests/${id}`, ElevationRequestSchema);
}

export function approveElevationRequest(id: number): Promise<ElevationRequest> {
  return request(`elevation-requests/${id}/approve`, ElevationRequestSchema, { method: "POST" });
}

export function denyElevationRequest(id: number, reason?: string): Promise<ElevationRequest> {
  return request(`elevation-requests/${id}/deny`, ElevationRequestSchema, {
    method: "POST",
    body: JSON.stringify(reason ? { reason } : {}),
  });
}

export type DeviceListParams = {
  enrollment_status?: string;
  group_id?: number;
  limit?: number;
  offset?: number;
};

export function listDevices(params: DeviceListParams = {}): Promise<DeviceList> {
  const search = new URLSearchParams();
  if (params.enrollment_status) search.set("enrollment_status", params.enrollment_status);
  if (params.group_id !== undefined) search.set("group_id", String(params.group_id));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const query = search.toString();
  return request(`devices${query ? `?${query}` : ""}`, DeviceListSchema);
}

export function assignDeviceGroup(deviceId: number, groupId: number | null): Promise<Device> {
  return request(`devices/${deviceId}/group`, DeviceSchema, {
    method: "PATCH",
    body: JSON.stringify({ group_id: groupId }),
  });
}

export function requestDeviceUpdate(deviceId: number): Promise<Device> {
  return request(`devices/${deviceId}/request-update`, DeviceSchema, { method: "POST" });
}

export function listDeviceGroups(): Promise<DeviceGroupList> {
  return request("device-groups", DeviceGroupListSchema);
}

export function createDeviceGroup(name: string, description?: string): Promise<DeviceGroup> {
  return request("device-groups", DeviceGroupSchema, {
    method: "POST",
    body: JSON.stringify({ name, description: description || undefined }),
  });
}

export async function deleteDeviceGroup(groupId: number): Promise<void> {
  await request(`device-groups/${groupId}`, z.unknown(), { method: "DELETE" });
}

export type AppAllowlistListParams = {
  group_id?: number;
};

export function listAppAllowlistEntries(
  params: AppAllowlistListParams = {},
): Promise<AppAllowlistEntryList> {
  const search = new URLSearchParams();
  if (params.group_id !== undefined) search.set("group_id", String(params.group_id));
  const query = search.toString();
  return request(`app-allowlist${query ? `?${query}` : ""}`, AppAllowlistEntryListSchema);
}

export function createAppAllowlistEntry(input: {
  publisher: string;
  filename: string;
  group_id?: number | null;
  description?: string;
}): Promise<AppAllowlistEntry> {
  return request("app-allowlist", AppAllowlistEntrySchema, {
    method: "POST",
    body: JSON.stringify({
      publisher: input.publisher,
      filename: input.filename,
      group_id: input.group_id ?? undefined,
      description: input.description || undefined,
    }),
  });
}

export async function deleteAppAllowlistEntry(entryId: number): Promise<void> {
  await request(`app-allowlist/${entryId}`, z.unknown(), { method: "DELETE" });
}

export function getDashboardAlerts(): Promise<AlertList> {
  return request("dashboard/alerts", AlertListSchema);
}

export function getEnrollmentInfo(): Promise<EnrollmentInfo> {
  return request("dashboard/enrollment-info", EnrollmentInfoSchema);
}

export type AuditLogListParams = {
  actor_type?: string;
  action?: string;
  target_type?: string;
  limit?: number;
  offset?: number;
};

export function listAuditLogs(params: AuditLogListParams = {}): Promise<AuditLogList> {
  const search = new URLSearchParams();
  if (params.actor_type) search.set("actor_type", params.actor_type);
  if (params.action) search.set("action", params.action);
  if (params.target_type) search.set("target_type", params.target_type);
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.offset !== undefined) search.set("offset", String(params.offset));
  const query = search.toString();
  return request(`audit-logs${query ? `?${query}` : ""}`, AuditLogListSchema);
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const body = await readBody(response);
  if (!response.ok) {
    throw new ApiError(response.status, extractErrorMessage(body, "Login failed."));
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}
