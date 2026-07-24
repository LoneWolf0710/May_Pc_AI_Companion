# ── Dual Ollama Startup Script for May AI ──────────────────────────────
# Starts two Ollama instances:
#   Port 11434 — Router (qwen3:0.6b, ~0.5GB VRAM) — always loaded
#   Port 11435 — Main (phi4-mini:3.8b, ~2.5GB VRAM) — complex reasoning
#
# Total VRAM: ~3.0GB (fits comfortably in 6GB with 3GB headroom)
#
# Usage:
#   .\start_ollama.ps1          # Start both instances
#   .\start_ollama.ps1 -Stop    # Stop both instances
#   .\start_ollama.ps1 -Status  # Check if running

param(
    [switch]$Stop,
    [switch]$Status,
    [switch]$Setup  # Create Modelfiles and pull models on first run
)

$OLLAMA_EXE = "ollama"
$ROUTER_PORT = 11434
$MAIN_PORT = 11435
$ROUTER_MODEL = "may-router:latest"
$MAIN_MODEL = "may-main:latest"
$BACKEND_DIR = Join-Path $PSScriptRoot "backend"
$OLLAMA_DATA = Join-Path $env:USERPROFILE ".may\ollama_dual"

# ── Status check ──────────────────────────────────────────────────────
function Get-OllamaStatus {
    $routerRunning = $false
    $mainRunning = $false
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:${ROUTER_PORT}/api/tags" -TimeoutSec 2
        $routerRunning = $true
    } catch {}
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:${MAIN_PORT}/api/tags" -TimeoutSec 2
        $mainRunning = $true
    } catch {}
    return @{
        Router = $routerRunning
        Main = $mainRunning
    }
}

if ($Status) {
    $status = Get-OllamaStatus
    Write-Host "Router (port ${ROUTER_PORT}): $(if ($status.Router) { 'Running' } else { 'Stopped' })" -ForegroundColor $(if ($status.Router) { 'Green' } else { 'Red' })
    Write-Host "Main (port ${MAIN_PORT}): $(if ($status.Main) { 'Running' } else { 'Stopped' })" -ForegroundColor $(if ($status.Main) { 'Green' } else { 'Red' })
    return
}

# ── Stop both instances ───────────────────────────────────────────────
if ($Stop) {
    Write-Host "Stopping dual Ollama instances..." -ForegroundColor Yellow
    # Kill any ollama processes on our ports
    $procs = Get-NetTCPConnection -LocalPort $ROUTER_PORT,$MAIN_PORT -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($pid in $procs) {
        if ($pid) {
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
            Write-Host "  Killed process $pid" -ForegroundColor Gray
        }
    }
    Write-Host "Done." -ForegroundColor Green
    return
}

# ── Setup: Create Modelfiles and pull models ──────────────────────────
if ($Setup) {
    Write-Host "Setting up dual Ollama instances for May..." -ForegroundColor Cyan

    $routerModelfile = Join-Path $BACKEND_DIR "llm\Modelfile.router"
    $mainModelfile = Join-Path $BACKEND_DIR "llm\Modelfile.main"

    if (!(Test-Path $routerModelfile)) {
        Write-Host "ERROR: Modelfile.router not found at $routerModelfile" -ForegroundColor Red
        return
    }
    if (!(Test-Path $mainModelfile)) {
        Write-Host "ERROR: Modelfile.main not found at $mainModelfile" -ForegroundColor Red
        return
    }

    Write-Host "`nCreating router model ($ROUTER_MODEL)..." -ForegroundColor Yellow
    Push-Location $BACKEND_DIR
    & $OLLAMA_EXE create $ROUTER_MODEL -f $routerModelfile
    Pop-Location

    Write-Host "`nCreating main model ($MAIN_MODEL)..." -ForegroundColor Yellow
    Push-Location $BACKEND_DIR
    & $OLLAMA_EXE create $MAIN_MODEL -f $mainModelfile
    Pop-Location

    Write-Host "`nSetup complete! Models created:" -ForegroundColor Green
    & $OLLAMA_EXE list | Select-String "may-"
    return
}

# ── Start both instances ──────────────────────────────────────────────
Write-Host "Starting dual Ollama instances for May..." -ForegroundColor Cyan

# Stop any existing instances on our ports first
$status = Get-OllamaStatus
if ($status.Router) {
    Write-Host "Router already running on port ${ROUTER_PORT}" -ForegroundColor Green
} else {
    # Start router instance
    Write-Host "Starting Router (port ${ROUTER_PORT}, model ${ROUTER_MODEL})..." -ForegroundColor Yellow
    $env:OLLAMA_HOST = "127.0.0.1:${ROUTER_PORT}"
    $env:OLLAMA_MODELS = $OLLAMA_DATA
    $env:OLLAMA_FLASH_ATTENTION = "1"
    $env:OLLAMA_KEEP_ALIVE = "24h"
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
    Start-Process -FilePath $OLLAMA_EXE -ArgumentList "serve" -NoNewWindow -PassThru | Out-Null
    Start-Sleep -Seconds 2

    # Wait for readiness
    for ($i = 0; $i -lt 10; $i++) {
        try {
            Invoke-RestMethod -Uri "http://localhost:${ROUTER_PORT}/api/tags" -TimeoutSec 1 | Out-Null
            Write-Host "Router ready on port ${ROUTER_PORT}" -ForegroundColor Green
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
}

if ($status.Main) {
    Write-Host "Main already running on port ${MAIN_PORT}" -ForegroundColor Green
} else {
    # Start main instance
    Write-Host "Starting Main (port ${MAIN_PORT}, model ${MAIN_MODEL})..." -ForegroundColor Yellow
    $env:OLLAMA_HOST = "127.0.0.1:${MAIN_PORT}"
    $env:OLLAMA_MODELS = $OLLAMA_DATA
    $env:OLLAMA_FLASH_ATTENTION = "1"
    $env:OLLAMA_KEEP_ALIVE = "24h"
    $env:OLLAMA_MAX_LOADED_MODELS = "1"
    Start-Process -FilePath $OLLAMA_EXE -ArgumentList "serve" -NoNewWindow -PassThru | Out-Null
    Start-Sleep -Seconds 2

    # Wait for readiness
    for ($i = 0; $i -lt 10; $i++) {
        try {
            Invoke-RestMethod -Uri "http://localhost:${MAIN_PORT}/api/tags" -TimeoutSec 1 | Out-Null
            Write-Host "Main ready on port ${MAIN_PORT}" -ForegroundColor Green
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
}

# Reset env vars
Remove-Item Env:OLLAMA_HOST -ErrorAction SilentlyContinue
Remove-Item Env:OLLAMA_MODELS -ErrorAction SilentlyContinue

Write-Host "`nDual Ollama instances started!" -ForegroundColor Green
Write-Host "  Router: http://localhost:${ROUTER_PORT} (${ROUTER_MODEL})" -ForegroundColor Gray
Write-Host "  Main:   http://localhost:${MAIN_PORT} (${MAIN_MODEL})" -ForegroundColor Gray
