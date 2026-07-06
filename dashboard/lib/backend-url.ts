import "server-only";

/**
 * The real FastAPI backend's base URL - read only in server-side code (Route Handlers), never
 * sent to the browser. This is the address our BFF proxy talks to; browser JS never sees it.
 */
export function getBackendUrl(): string {
  const url = process.env.BACKEND_URL;
  if (!url) {
    throw new Error("BACKEND_URL is not configured. Set it in .env.local (see .env.example).");
  }
  return url.replace(/\/+$/, "");
}
