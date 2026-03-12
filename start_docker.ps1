#!/usr/bin/env pwsh

<#
.SYNOPSIS
    Inicia o Elion MDM via Docker Compose (Desenvolvimento)
.DESCRIPTION
    Script que simplifica o start do ambiente Docker para o projeto MDM
.EXAMPLE
    .\start_docker.ps1
    .\start_docker.ps1 -Down    # Para os containers
    .\start_docker.ps1 -Build   # Rebuilda as imagens
#>

param(
    [switch]$Down,
    [switch]$Build,
    [switch]$Logs,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================`n🐳 Elion MDM - Docker Compose`n=========================================`n" -ForegroundColor Cyan

# Verificar se Docker está instalado
try {
    $dockerVersion = docker --version
    Write-Host "✅ Docker disponível: $dockerVersion`n" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker não está instalado ou não está no PATH" -ForegroundColor Red
    exit 1
}

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectPath

# Ações
if ($Down) {
    Write-Host "[1] Parando Docker Compose..." -ForegroundColor Yellow
    docker-compose down -v
    Write-Host "✅ Containers parados e volumes removidos`n" -ForegroundColor Green
    exit 0
}

if ($Clean) {
    Write-Host "[1] Removendo volumes, imagens e networks..." -ForegroundColor Yellow
    docker-compose down -v --remove-orphans
    docker system prune -f
    Write-Host "✅ Ambiente limpo`n" -ForegroundColor Green
    exit 0
}

if ($Build) {
    Write-Host "[1] Rebuilding imagens Docker..." -ForegroundColor Yellow
    docker-compose build --no-cache
    Write-Host "✅ Imagens construídas`n" -ForegroundColor Green
}

if ($Logs) {
    Write-Host "[1] Exibindo logs em tempo real...`n" -ForegroundColor Yellow
    Write-Host "Pressione Ctrl+C para sair`n"
    docker-compose logs -f
    exit 0
}

# ======= INÍCIO NORMAL =======

Write-Host "[1/3] Iniciando Docker Compose...`n" -ForegroundColor Yellow

# Carregar variáveis do .env
if (!(Test-Path ".env")) {
    Write-Host "⚠️  Arquivo .env não encontrado. Copie do template." -ForegroundColor Yellow
    exit 1
}

# Iniciar containers
docker-compose up -d

# Aguardar containers ficarem prontos
Write-Host "`n[2/3] Aguardando inicialização dos containers..." -ForegroundColor Yellow
Start-Sleep -Seconds 12
Write-Host "✅ Containers iniciados`n" -ForegroundColor Green

# Exibir URLs de acesso
Write-Host "`n[3/3] Ambiente iniciado! Acesse:" -ForegroundColor Yellow
Write-Host "════════════════════════════════════════`n"
Write-Host "  Frontend (Nginx):    http://localhost" -ForegroundColor Cyan
Write-Host "  Backend API:         http://localhost/api" -ForegroundColor Cyan
Write-Host "  PostgreSQL:          localhost:5432`n" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════`n"

Write-Host "Comandos úteis:`n" -ForegroundColor Yellow
Write-Host "  Ver logs:              .\start_docker.ps1 -Logs`n"
Write-Host "  Parar containers:      .\start_docker.ps1 -Down`n"
Write-Host "  Rebuild imagens:       .\start_docker.ps1 -Build`n"
Write-Host "  Limpar tudo:           .\start_docker.ps1 -Clean`n"

Write-Host ""
docker-compose ps --format "table {{.Service}}\t{{.Status}}"
