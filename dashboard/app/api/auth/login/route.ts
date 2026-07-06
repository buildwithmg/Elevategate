import { NextResponse } from "next/server";

import { setSessionCookie } from "@/lib/auth";
import { getBackendUrl } from "@/lib/backend-url";

/**
 * Proxies to the real FastAPI login endpoint, then re-packages the returned JWT as an httpOnly
 * cookie instead of returning it in the response body - the token never reaches browser JS.
 */
export async function POST(request: Request) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Malformed request body." }, { status: 400 });
  }

  const backendResponse = await fetch(`${getBackendUrl()}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await backendResponse.json().catch(() => null);

  if (!backendResponse.ok || !data?.access_token) {
    return NextResponse.json(
      data ?? { detail: "Login failed." },
      { status: backendResponse.status || 502 },
    );
  }

  await setSessionCookie(data.access_token as string);
  return NextResponse.json({ ok: true });
}
