# ElevateGate Dashboard

A Next.js (App Router) dashboard for IT administrators to review and approve/deny Windows
endpoint privilege elevation requests, talking to the [ElevateGate FastAPI backend](../backend).

See also: [docs/API_CONTRACT.md](../docs/API_CONTRACT.md) (the backend contract this dashboard is
built against) and [docs/BACKEND_THREAT_MODEL.md](../docs/BACKEND_THREAT_MODEL.md).

## Stack

Next.js 16 (App Router, Turbopack), TypeScript, Tailwind CSS v4, shadcn/ui (Base UI primitives),
TanStack Query v5, Zod v4.

> **This project scaffolded onto a genuinely newer Next.js than most training data reflects** —
> `middleware.ts` is deprecated and renamed to **`proxy.ts`** (exported function `proxy`, not
> `middleware`), and this repo's shadcn/ui preset ("Nova") generates components on `@base-ui/react`
> rather than Radix, which uses a `render={<Element />}` prop instead of `asChild` for composing a
> trigger with a custom element. Both surprised me during development; noted here so a future
> reader isn't caught by the same thing.

## Architecture: no token ever reaches the browser

The spec asked to avoid `localStorage` for the access token "if a safer architecture is
available" — one is. This app is a thin **BFF (backend-for-frontend)**:

1. `POST /api/auth/login` (a Next.js Route Handler) calls the real FastAPI
   `POST /api/v1/auth/login`, then stores the returned JWT as an **httpOnly, Secure,
   SameSite=Lax** cookie on the dashboard's own origin. The cookie's `maxAge` is computed from the
   JWT's own `exp` claim (decoded, not verified — verification is the backend's job).
2. **`app/api/backend/[...path]/route.ts`** is the *only* way any dashboard code reaches the
   FastAPI backend. It reads the httpOnly cookie server-side, attaches
   `Authorization: Bearer <token>`, and forwards to `${BACKEND_URL}/api/v1/<path>`. Every
   `lib/api-client.ts` function calls this same-origin proxy — never the backend directly. The
   browser never learns the backend's URL, and JavaScript can never read the token (that's what
   `httpOnly` means).
3. `proxy.ts` (the file formerly known as `middleware.ts`) does an **optimistic** check — cookie
   present or not — to redirect `/login` ↔ the dashboard before a page even renders. This is a UX
   nicety, not the security boundary: the real authorization check happens on every actual data
   call, for real, on the FastAPI backend, which validates the JWT's signature and expiry itself.
   A `401` from the backend clears the cookie and the client redirects to `/login`.
4. SameSite=Lax on a same-origin-only, POST-based proxy already blocks the classic cross-site CSRF
   vector (Lax cookies aren't attached to cross-site POSTs) — no separate CSRF token scheme was
   added on top of that.

There is exactly one environment variable (`BACKEND_URL`), and it's never prefixed
`NEXT_PUBLIC_` — there's no reason for the browser to ever know it.

## Getting started

```bash
npm install
cp .env.example .env.local   # defaults to http://localhost:8000, matching the backend's default
npm run dev
```

You need the [ElevateGate backend](../backend) running locally (Postgres + `uvicorn
app.main:app`) and at least one admin seeded (`python -m scripts.seed_admin` in `backend/`).

## Verification run during development

- `npm run lint`, `npx tsc --noEmit`, and `npm run build` all pass clean, re-run after every page
  was added.
- The full flow was exercised against the **real** local backend (real Postgres, real seeded
  admin): log in, dashboard summary cards render live counts, submit a test elevation request via
  the backend's device API directly, watch it appear via the 5-second poll with a toast + row
  highlight, open its detail page, approve it (confirmation dialog shows the exact required copy
  and the SHA-256/publisher/device), and confirm devices/audit-logs reflect the resulting rows.
  Also confirmed: the sidebar's pending-count badge scrolls independently of a fixed sidebar
  (caught and fixed a layout bug where the whole page scrolled together), toast placement doesn't
  overlap the header's user menu (caught and fixed), the httpOnly cookie is genuinely invisible to
  `document.cookie`, and logging out actually clears the session server-side (a stale client after
  logout gets redirected to `/login` by the proxy, not just by client-side state).
- **One real finding worth calling out**: TanStack Query pauses `refetchInterval` by default when
  the tab is backgrounded (`document.hidden`). That's the right default for most of this app's
  polling, but wrong for the specific query that drives the "new request" toast - the whole point
  of a notification is to catch something while looking elsewhere. `pending-requests-context.tsx`
  sets `refetchIntervalInBackground: true` on that one query only, verified by triggering a new
  request via `curl` while the tab was backgrounded and confirming the toast still fired.

## Known gaps / honest limitations

- **The `Failed` status badge is unreachable with real data today.** The UI spec's status list
  includes `Pending / Approved / Denied / Expired / Failed`, but the backend's
  `ElevationRequestStatus` enum only ever produces the first four — `Failed` is a concept that
  currently only exists on the Windows agent's side (a request it locally couldn't execute) and
  has no path to reach this backend/dashboard yet. The badge variant exists and is styled, ready
  for whenever that's wired up.
- **Two small, well-justified backend additions were made to build this dashboard for real**
  rather than mocking three pages permanently: `GET /api/v1/devices`, `GET /api/v1/audit-logs`,
  `GET /api/v1/dashboard/summary`, and `device_uuid`/`device_hostname` were added to
  `ElevationRequestRead` (previously only a bare internal `device_id`). All are documented in
  `docs/API_CONTRACT.md` and covered by real backend tests (`backend/tests/integration/`).
- Rate limiting, audit logging, and RBAC are enforced by the backend, not re-implemented here —
  this app trusts the backend as the actual authority on every one of those, by design.

## Project layout

```
app/
  login/page.tsx                         public
  (dashboard)/layout.tsx                  sidebar + header shell, wraps every other page
  (dashboard)/page.tsx                     Dashboard: summary cards + recent requests
  (dashboard)/elevation-requests/page.tsx           table + status filter tabs
  (dashboard)/elevation-requests/[id]/page.tsx        detail + Approve Once / Deny
  (dashboard)/devices/page.tsx
  (dashboard)/audit-logs/page.tsx           filters + pagination
  (dashboard)/settings/page.tsx
  api/auth/login, api/auth/logout, api/backend/[...path]   the BFF proxy (see above)
  proxy.ts                                   optimistic route protection
lib/
  schemas.ts        Zod schemas mirroring the backend's actual response shapes (snake_case)
  api-client.ts       fetch wrappers -> the proxy, every response parsed through Zod
  auth.ts               server-only cookie/JWT-claim helpers
  backend-url.ts          reads BACKEND_URL (server-only)
  pending-requests-context.tsx   the 5s poll + new-request toast/highlight, mounted once
components/
  ui/                (shadcn)
  layout/, shared/, elevation-requests/, dashboard/, devices/, audit-logs/
```
