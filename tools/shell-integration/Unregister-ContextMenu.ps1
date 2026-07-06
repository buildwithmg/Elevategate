#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Removes the "Request IT Approval" Explorer context-menu verb added by Register-ContextMenu.ps1.
#>

$ErrorActionPreference = "Stop"

function Unregister-Verb {
    param([string]$ProgId)

    $verbKey = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Classes\$ProgId\shell\ElevateGateRequest"
    if (Test-Path $verbKey) {
        Remove-Item -Path $verbKey -Recurse -Force
        Write-Host "Removed 'Request IT Approval' verb from $ProgId."
    }
}

Unregister-Verb -ProgId "exefile"
Unregister-Verb -ProgId "Msi.Package"
