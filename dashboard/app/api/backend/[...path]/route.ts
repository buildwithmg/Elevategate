import { NextResponse } from "next/server";

import { clearSessionCookie, getSessionToken } from "@/lib/auth";
import { getBackendUrl } from "@/lib/backend-url";

/**
 * The single point of contact between the browser and the real FastAPI backend. Every dashboard
 * data call goes through this route: it reads the httpOnly session cookie server-side, attaches
 * it as `Authorization: Bearer <token>`, forwards to `${BACKEND_URL}/api/v1/<path>`, and relays
 * the JSON response and status code back verbatim. The browser never sees the backend's URL or
 * the JWT itself - only ever talks to this same-origin route.
 */

type RouteParams = { params: Promise<{ path: string[] }> };

async function forward(request: Request, { params }: RouteParams): Promise<NextResponse> {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated." }, { status: 401 });
  }

  const { path } = await params;
  const search = new URL(request.url).search;
  const targetUrl = `${getBackendUrl()}/api/v1/${path.join("/")}${search}`;

  const init: RequestInit = {
    method: request.method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(request.method !== "GET" && request.method !== "HEAD"
        ? { "Content-Type": "application/json" }
        : {}),
    },
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const bodyText = await request.text();
    if (bodyText) init.body = bodyText;
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(targetUrl, init);
  } catch {
    return NextResponse.json({ detail: "Could not reach the backend." }, { status: 502 });
  }

  if (backendResponse.status === 401) {
    // The backend is the authority on token validity (expiry, revocation) - if it says our
    // session is no longer good, clear it here too so the proxy's optimistic cookie-presence
    // check reflects reality on the very next navigation.
    await clearSessionCookie();
  }

  const responseText = await backendResponse.text();
  return new NextResponse(responseText || null, {
    status: backendResponse.status,
    headers: { "Content-Type": backendResponse.headers.get("Content-Type") ?? "application/json" },
  });
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
