#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Stops and removes the ElevateGate Agent Windows Service, context-menu registration, and
    install directory.

.PARAMETER KeepData
    If set, leaves $env:ProgramData\ElevateGate (audit log, nonce ledger, device credential) in
    place instead of deleting it.
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\ElevateGate",
    [string]$ServiceName = "ElevateGateAgent",
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Write-Host "Stopping and removing service '$ServiceName'..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
}

Write-Host "Removing Explorer context menu..."
& (Join-Path $PSScriptRoot "..\shell-integration\Unregister-ContextMenu.ps1")

if (Test-Path $InstallDir) {
    Write-Host "Removing install directory $InstallDir..."
    Remove-Item -Path $InstallDir -Recurse -Force
}

if (-not $KeepData) {
    $dataDir = "$env:ProgramData\ElevateGate"
    if (Test-Path $dataDir) {
        Write-Host "Removing local data directory $dataDir..."
        Remove-Item -Path $dataDir -Recurse -Force
    }
}

Write-Host "ElevateGate Agent uninstalled."
