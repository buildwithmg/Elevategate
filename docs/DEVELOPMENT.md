# Development Setup

## Prerequisites

- .NET 8 SDK.
- Windows is required to *run* `ElevateGate.Service` and `ElevateGate.Tray` — they target
  `net8.0-windows`, use WinForms, Windows Services, DPAPI, named pipes, and WinTrust. This is not
  optional; the security model depends on these being real Windows primitives.

## What was actually verified where

This project was developed on **macOS**. That matters for what "tested" means here, so it's
stated plainly rather than implied:

- **`ElevateGate.Core` and `ElevateGate.Infrastructure`** are plain `net8.0` class libraries with
  no Windows-specific dependencies. They were built *and* unit-tested on macOS with real,
  passing `dotnet test` runs — including `ApprovalTokenValidator` (signature/expiry/nonce/hash
  rejection paths), `PathValidator` (traversal/UNC/removable-drive rejection), `Sha256FileHasher`,
  `Ed25519Verifier`, and the SQLite-backed nonce store and audit log. These are the components
  that decide whether something gets executed, so this is where the test coverage is concentrated.
- **`ElevateGate.Service` and `ElevateGate.Tray`** target `net8.0-windows` (the latter also uses
  WinForms). Setting `<EnableWindowsTargeting>true</EnableWindowsTargeting>` in both `.csproj`
  files lets `dotnet build` **compile** them on macOS too — and it does, cleanly, with zero
  warnings — which caught real interop/API mistakes during development (P/Invoke signatures, the
  `System.IO.Pipes.AccessControl` package not resolving cross-platform, `X509Certificate2` API
  shape, WinForms designer generator requirements). **What compiling on macOS cannot verify** is
  runtime behavior: whether the Windows Service actually installs and starts, whether DPAPI
  actually round-trips a secret, whether the named pipe ACL and client-identity checks actually
  admit/reject the right processes, whether `WinVerifyTrust` returns what's expected for a real
  signed/unsigned file, or whether the WinForms UI actually looks and behaves correctly. Those
  need a real Windows machine — see the checklist below.

## Building

```bash
dotnet build
```

Builds the whole solution, including the Windows-only projects (cross-compiled if you're not on
Windows).

## Running the tests

```bash
dotnet test
```

Runs `ElevateGate.Core.Tests` and `ElevateGate.Infrastructure.Tests`. Both run on any OS with the
.NET 8 SDK.

## Manual verification checklist (requires a real Windows machine)

Run this after any change to `ElevateGate.Service` or `ElevateGate.Tray`, since neither project's
runtime behavior can be exercised anywhere else:

1. `tools\install\Install-ElevateGate.ps1 -BackendBaseUrl <url> -ServerPublicKeyBase64 <key>` as
   Administrator; confirm the service installs, starts, and shows up in `services.msc` as
   `ElevateGate Agent`, running as `Local System`.
2. Confirm `%ProgramData%\ElevateGate\device-credential.json` is created on first start, and that
   its `protectedBearerTokenBase64` value is **not** the plaintext token (DPAPI round-trip).
3. Right-click any `.exe` or `.msi` file in Explorer; confirm "Request IT Approval" appears and
   launches the tray with that file pre-filled.
4. Submit a request from the tray with the service's pipe not yet reachable (e.g. service
   stopped) and confirm the tray reports a clear failure rather than hanging.
5. With a real (or stubbed) backend reachable, submit a request, approve it from the backend side,
   and confirm: the file actually launches, the tray shows "Approved," and a balloon notification
   appears.
6. Repeat with a denial and confirm the tray shows "Denied" with a notification and nothing
   executes.
7. Try replaying an already-used approval token (e.g. by restarting the polling worker's watermark
   or replaying a captured decision payload) and confirm it's rejected — check
   `%ProgramData%\ElevateGate\audit.db` for a `ValidationRejected` row with the nonce-reuse reason.
8. Try requesting a file on a USB drive and a file on a mapped network drive; confirm both are
   rejected before ever reaching the backend.
9. Confirm an unsigned `.exe`'s request still reaches the backend with
   `signature.trustStatus: "unsigned"` rather than being silently treated as trusted.

## Project layout

See the table in [README.md](../README.md#architecture).
