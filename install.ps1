<#
.SYNOPSIS
    One-line installer for ElevateGate Agent. Downloads the latest pre-built release (no .NET
    SDK, no git clone required) and installs the Windows Service + Explorer context-menu verb.

.DESCRIPTION
    Run this from any PowerShell prompt (elevated or not - it re-launches itself elevated if
    needed):

        irm https://raw.githubusercontent.com/buildwithmg/Elevategate/main/install.ps1 | iex

    You'll be prompted once for the enrollment key (given to you by whoever runs the ElevateGate
    backend) - everything else (backend URL, pinned server public key) is baked into the release.
#>

$ErrorActionPreference = "Stop"

# --- Self-elevate if needed --------------------------------------------------------------------
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Re-launching elevated (installing a Windows Service requires Administrator)..."
    $bootstrapUrl = "https://raw.githubusercontent.com/buildwithmg/Elevategate/main/install.ps1"
    $elevatedCommand = "irm $bootstrapUrl | iex"
    Start-Process powershell.exe -Verb RunAs -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $elevatedCommand)
    exit
}

# --- Enrollment key -----------------------------------------------------------------------------
$enrollmentKey = $env:ELEVATEGATE_ENROLLMENT_KEY
if ([string]::IsNullOrWhiteSpace($enrollmentKey)) {
    $secure = Read-Host "Enter your ElevateGate enrollment key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $enrollmentKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}
if ([string]::IsNullOrWhiteSpace($enrollmentKey)) { throw "An enrollment key is required." }

# --- Download the latest release -------------------------------------------------------------
$repo = "buildwithmg/Elevategate"
Write-Host "Looking up the latest release of $repo..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers @{ "User-Agent" = "ElevateGate-Installer" }
$asset = $release.assets | Where-Object { $_.name -like "ElevateGate-Agent-*-win-x64.zip" } | Select-Object -First 1
if (-not $asset) { throw "No win-x64 release asset found on the latest release ($($release.tag_name))." }

$workDir = Join-Path $env:TEMP "ElevateGateInstall"
Remove-Item $workDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$zipPath = Join-Path $workDir $asset.name

Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size / 1MB, 1)) MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -Headers @{ "User-Agent" = "ElevateGate-Installer" }

Write-Host "Extracting..."
$extractDir = Join-Path $workDir "extracted"
Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

# --- Install --------------------------------------------------------------------------------
$installScript = Join-Path $extractDir "Install-FromRelease.ps1"
if (-not (Test-Path $installScript)) { throw "Install-FromRelease.ps1 not found in the release package." }

# Run in a child process with the policy bypassed just for this invocation - most machines default
# to a Restricted/AllSigned execution policy that blocks loading a .ps1 *file* from disk (unlike
# the `irm | iex` above, which evaluates a string and isn't subject to that same restriction).
# This does not change the machine's execution policy at all, only this one process.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installScript -EnrollmentKey $enrollmentKey
if ($LASTEXITCODE -ne 0) { throw "Install-FromRelease.ps1 failed (exit code $LASTEXITCODE)." }

Write-Host ""
Write-Host "Done. Cleaning up..."
Remove-Item $workDir -Recurse -Force -ErrorAction SilentlyContinue
