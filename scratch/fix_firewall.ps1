# Run this script in PowerShell as Administrator.

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Error "Execute este script como Administrador."
    exit 1
}

$rules = @(
    @{
        DisplayName = "Elion MDM - HTTP"
        LocalPort = "80,8080"
        Protocol = "TCP"
    },
    @{
        DisplayName = "Elion MDM - Backend"
        LocalPort = "8200"
        Protocol = "TCP"
    }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.DisplayName -ErrorAction SilentlyContinue

    if ($existing) {
        Write-Host "Regra ja existe: $($rule.DisplayName)"
        continue
    }

    New-NetFirewallRule `
        -DisplayName $rule.DisplayName `
        -Direction Inbound `
        -LocalPort $rule.LocalPort `
        -Protocol $rule.Protocol `
        -Action Allow | Out-Null

    Write-Host "Regra criada: $($rule.DisplayName) portas $($rule.LocalPort)"
}

Write-Host "Firewall configurado para o Elion MDM."
