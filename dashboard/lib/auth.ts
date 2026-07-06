import "server-only";

import { cookies } from "next/headers";

/**
 * Server-only session handling. The cookie's value IS the FastAPI-issued JWT, stored verbatim -
 * we never mint our own session token. Signature verification of that JWT happens for real on
 * the backend on every proxied request (app/api/backend/[...path]/route.ts); nothing here trusts
 * the token's contents for authorization, only reads its `exp` claim to size the cookie's
 * lifetime.
 */
export const SESSION_COOKIE_NAME = "eg_session";

/** Decodes (never verifies - the backend is the source of truth) a JWT's payload. */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payloadSegment] = token.split(".");
    if (!payloadSegment) return null;
    const base64 = payloadSegment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    const json = Buffer.from(padded, "base64").toString("utf-8");
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Seconds until the token's `exp` claim, clamped to a sane range. Falls back to 30 minutes if `exp` is missing/unparseable. */
function secondsUntilExpiry(token: string): number {
  const FALLBACK_SECONDS = 30 * 60;
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === "number" ? payload.exp : null;
  if (exp === null) return FALLBACK_SECONDS;

  const remaining = exp - Math.floor(Date.now() / 1000);
  return remaining > 0 ? remaining : 0;
}

export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: secondsUntilExpiry(token),
  });
}

export async function getSessionToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get(SESSION_COOKIE_NAME)?.value;
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}
