#!/usr/bin/env pwsh

<#
.SYNOPSIS
    Elion MDM – Docker Compose helper (dev & prod)
.EXAMPLE
    .\start_docker.ps1              # Sobe ambiente dev
    .\start_docker.ps1 -Build       # Rebuilda imagens
    .\start_docker.ps1 -Down        # Para tudo (remove volumes)
    .\start_docker.ps1 -Logs        # Acompanha logs
    .\start_docker.ps1 -Prod        # Sobe ambiente de produção
    .\start_docker.ps1 -CreateAdmin # Cria usuário admin
#>

param(
    [switch]$Down,
    [switch]$Build,
    [switch]$Logs,
    [switch]$Clean,
    [switch]$Prod,
    [switch]$CreateAdmin
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================`n  Elion MDM - Docker Compose`n=========================================`n" -ForegroundColor Cyan

# ── Verificar Docker ─────────────────────
try {
    $dockerVersion = docker --version
    Write-Host "[OK] Docker: $dockerVersion`n" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] Docker nao esta instalado ou nao esta no PATH" -ForegroundColor Red
    exit 1
}

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectPath

# Compose files
$composeFiles = @("-f", "docker-compose.yml")
if ($Prod) { $composeFiles += @("-f", "docker-compose.prod.yml") }

# ── Ações ────────────────────────────────
if ($Down) {
    Write-Host "[1] Parando Docker Compose..." -ForegroundColor Yellow
    docker compose @composeFiles down -v
    Write-Host "[OK] Containers parados e volumes removidos`n" -ForegroundColor Green
    exit 0
}

if ($Clean) {
    Write-Host "[1] Removendo volumes, imagens e networks..." -ForegroundColor Yellow
    docker compose @composeFiles down -v --remove-orphans
    docker system prune -f
    Write-Host "[OK] Ambiente limpo`n" -ForegroundColor Green
    exit 0
}

if ($Build) {
    Write-Host "[1] Rebuilding imagens Docker..." -ForegroundColor Yellow
    docker compose @composeFiles build --no-cache
    Write-Host "[OK] Imagens construidas`n" -ForegroundColor Green
}

if ($Logs) {
    Write-Host "[1] Exibindo logs em tempo real...`n" -ForegroundColor Yellow
    Write-Host "Pressione Ctrl+C para sair`n"
    docker compose @composeFiles logs -f
    exit 0
}

if ($CreateAdmin) {
    Write-Host "[1] Criando usuario admin..." -ForegroundColor Yellow
    docker compose exec backend python -m backend.create_admin --email admin@mdm.com --password $env:DEFAULT_ADMIN_PASSWORD
    exit 0
}

# Verificar .env
if (!(Test-Path ".env")) {
    Write-Host "[AVISO] .env nao encontrado. Copiando do template..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "[OK] .env criado a partir do .env.example - EDITE as senhas antes de continuar!" -ForegroundColor Yellow
        exit 1
    }
    else {
        Write-Host "[ERRO] .env.example tambem nao encontrado." -ForegroundColor Red
        exit 1
    }
}

# ── Subir containers ─────────────────────
$modeLabel = if ($Prod) { "PRODUCAO" } else { "DESENVOLVIMENTO" }
Write-Host "`n[1/3] Iniciando Docker Compose ($modeLabel)...`n" -ForegroundColor Yellow

docker compose @composeFiles up -d

# ── Aguardar ─────────────────────────────
Write-Host "`n[2/3] Aguardando inicializacao..." -ForegroundColor Yellow
Start-Sleep -Seconds 12
Write-Host "[OK] Containers iniciados`n" -ForegroundColor Green

# ── URLs ─────────────────────────────────
Write-Host "`n[3/3] Ambiente iniciado! Acesse:" -ForegroundColor Yellow
Write-Host "========================================`n"
Write-Host "  Frontend (Vite dev):   http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Frontend (Nginx):      http://localhost" -ForegroundColor Cyan
Write-Host "  Backend API:           http://localhost/api" -ForegroundColor Cyan
Write-Host "  API Docs (Swagger):    http://localhost/api/docs" -ForegroundColor Cyan
Write-Host "  PostgreSQL:            localhost:5432`n" -ForegroundColor Cyan
Write-Host "========================================`n"

Write-Host "Comandos uteis:`n" -ForegroundColor Yellow
Write-Host "  Ver logs:              .\start_docker.ps1 -Logs"
Write-Host "  Parar containers:      .\start_docker.ps1 -Down"
Write-Host "  Rebuild imagens:       .\start_docker.ps1 -Build"
Write-Host "  Limpar tudo:           .\start_docker.ps1 -Clean"
Write-Host "  Criar admin:           .\start_docker.ps1 -CreateAdmin"
Write-Host "  Modo producao:         .\start_docker.ps1 -Prod`n"

Write-Host ""
docker compose @composeFiles ps --format "table {{.Service}}\t{{.Status}}"
