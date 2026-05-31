#Requires -Version 5.1
<#
.SYNOPSIS
    Solvy - BancoSol Agent - Setup automatico
.DESCRIPTION
    Levanta Redis, PostgreSQL y Evolution API via Docker Compose,
    escribe la configuracion del agente, registra la instancia de
    WhatsApp y el webhook, e instala las dependencias de Python.
    Al final ofrece generar un ZIP listo para compartir.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# --------------------------------------------------------------------------
# Helpers de consola
# --------------------------------------------------------------------------

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Solvy - BancoSol Agent  Setup v1.0     |" -ForegroundColor Cyan
    Write-Host "  |  Evolution API v2.3.7 + Redis + Postgres |" -ForegroundColor Cyan
    Write-Host "  +------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Header([string]$title) {
    Write-Host ""
    Write-Host ("  " + ("=" * 50)) -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host ("  " + ("=" * 50)) -ForegroundColor DarkCyan
    Write-Host ""
}

function Write-Step([string]$n, [string]$total, [string]$msg) {
    Write-Host "  [$n/$total] $msg" -ForegroundColor Yellow
}

function Write-OK([string]$msg)   { Write-Host "         OK  $msg" -ForegroundColor Green }
function Write-Skip([string]$msg) { Write-Host "         --  $msg" -ForegroundColor DarkGray }
function Write-Fail([string]$msg) { Write-Host "         !!  $msg" -ForegroundColor Red }

function Ask([string]$prompt, [string]$default = "") {
    if ($default) {
        $val = Read-Host "  $prompt [$default]"
    } else {
        $val = Read-Host "  $prompt"
    }
    if ([string]::IsNullOrWhiteSpace($val)) { return $default }
    return $val.Trim()
}

function AskRequired([string]$prompt) {
    $val = Read-Host "  $prompt"
    while ([string]::IsNullOrWhiteSpace($val)) {
        Write-Host "  Este campo es requerido." -ForegroundColor Red
        $val = Read-Host "  $prompt"
    }
    return $val.Trim()
}

# --------------------------------------------------------------------------
# PRE-CHECKS
# --------------------------------------------------------------------------

Write-Banner
Write-Header "PRE-CHECKS"

# Docker Desktop
Write-Step "1" "3" "Verificando Docker Desktop..."
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Docker Desktop no esta corriendo o no esta instalado."
    Write-Host "  Descargalo desde: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Write-Host "  Inicialo y volve a correr este script." -ForegroundColor Yellow
    exit 1
}
Write-OK "Docker Desktop esta corriendo."

# Python
Write-Step "2" "3" "Verificando Python..."
$pyVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Python no encontrado en PATH."
    Write-Host "  Descargalo desde: https://www.python.org/downloads/ (3.11 o superior)" -ForegroundColor Yellow
    exit 1
}
Write-OK "$pyVer"

# docker-compose.yml
Write-Step "3" "3" "Verificando docker-compose.yml..."
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
if (-not (Test-Path $ComposeFile)) {
    Write-Fail "docker-compose.yml no encontrado en: $ScriptDir"
    exit 1
}
Write-OK "docker-compose.yml encontrado."

# --------------------------------------------------------------------------
# CONFIGURACION
# --------------------------------------------------------------------------

Write-Header "CONFIGURACION"
Write-Host "  Completa los datos. Enter para aceptar el valor entre [corchetes]." -ForegroundColor DarkGray
Write-Host ""

# API key de Evolution - se genera una aleatoria como default
$chars = (48..57) + (97..102)   # 0-9, a-f  (hex)
$defaultApiKey = -join (1..32 | ForEach-Object { [char]($chars | Get-Random) })

$EvolutionApiKey = Ask "Evolution API Key (generada automaticamente)" $defaultApiKey

$OpenRouterApiKey = AskRequired "OpenRouter API Key  (sk-or-v1-...)"

Write-Host ""
Write-Host "  Numeros de WhatsApp que el bot aceptara (codigo de pais sin +)." -ForegroundColor DarkGray
Write-Host "  Ejemplo: 59160879844,59175572528" -ForegroundColor DarkGray
$AllowedNumbers = AskRequired "Numeros autorizados (separados por coma)"

Write-Host ""
Write-Host "  Numero del SolvyCall al que llegan los casos derivados." -ForegroundColor DarkGray
$SupportNumber = AskRequired "Numero de soporte"

Write-Host ""
Write-Host "  Ruta completa a la carpeta 'Problemas' del KB de BancoSol." -ForegroundColor DarkGray
Write-Host "  Debe contener los archivos PROB-001.md ... PROB-240.md" -ForegroundColor DarkGray
$defaultKbPath = "C:\Users\$env:USERNAME\Documents\BancoSol_KB\Problemas"
$KbPath = Ask "Ruta al KB (carpeta Problemas)" $defaultKbPath

$AgentPort     = Ask "Puerto del agente" "3000"
$InactivityHrs = Ask "Horas de inactividad para reset automatico" "24"

Write-Host ""
Write-Host "  Configuracion lista." -ForegroundColor Green

# --------------------------------------------------------------------------
# ESCRIBIR ARCHIVOS DE CONFIGURACION
# --------------------------------------------------------------------------

Write-Header "ESCRIBIENDO CONFIGURACION"

# .env raiz -> Docker Compose lee esto para sustituir ${EVOLUTION_API_KEY}
Write-Step "1" "3" "Escribiendo .env (Docker Compose)..."
Set-Content -Path (Join-Path $ScriptDir ".env") -Value "EVOLUTION_API_KEY=$EvolutionApiKey" -Encoding UTF8
Write-OK ".env raiz escrito."

# agent/.env -> lo lee el agente Python
Write-Step "2" "3" "Escribiendo agent\.env..."
$AgentEnvPath = Join-Path $ScriptDir "agent\.env"
$agentEnvLines = @(
    "EVOLUTION_URL=http://localhost:8080",
    "EVOLUTION_API_KEY=$EvolutionApiKey",
    "EVOLUTION_INSTANCE=banco-prueba",
    "",
    "OPENROUTER_API_KEY=$OpenRouterApiKey",
    "LLM_MODEL=openrouter/owl-alpha",
    "",
    "OBSIDIAN_KB_PATH=$KbPath",
    "",
    "ALLOWED_NUMBERS=$AllowedNumbers",
    "SUPPORT_NUMBER=$SupportNumber",
    "",
    "AGENT_PORT=$AgentPort",
    "INACTIVITY_HOURS=$InactivityHrs"
)
Set-Content -Path $AgentEnvPath -Value ($agentEnvLines -join "`n") -Encoding UTF8
Write-OK "agent\.env escrito."

# agent/.env.example -> va al ZIP, sin valores reales
Write-Step "3" "3" "Escribiendo agent\.env.example..."
$envExampleLines = @(
    "EVOLUTION_URL=http://localhost:8080",
    "EVOLUTION_API_KEY=REEMPLAZA_CON_TU_CLAVE_EVOLUTION",
    "EVOLUTION_INSTANCE=banco-prueba",
    "",
    "OPENROUTER_API_KEY=REEMPLAZA_CON_TU_API_KEY_OPENROUTER",
    "LLM_MODEL=openrouter/owl-alpha",
    "",
    "OBSIDIAN_KB_PATH=C:\ruta\completa\a\la\carpeta\Problemas",
    "",
    "ALLOWED_NUMBERS=59160000000,59160000001",
    "SUPPORT_NUMBER=59170000000",
    "",
    "AGENT_PORT=3000",
    "INACTIVITY_HOURS=24"
)
Set-Content -Path (Join-Path $ScriptDir "agent\.env.example") -Value ($envExampleLines -join "`n") -Encoding UTF8
Write-OK "agent\.env.example escrito."

# --------------------------------------------------------------------------
# DIRECTORIOS DE DATOS
# --------------------------------------------------------------------------

Write-Header "PREPARANDO DIRECTORIOS"
Write-Step "1" "1" "Creando carpetas data\..."

$dataDirs = @(
    "data\postgres",
    "data\redis",
    "data\evolution\instances",
    "data\evolution\store"
)
foreach ($dir in $dataDirs) {
    $fullPath = Join-Path $ScriptDir $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Force -Path $fullPath | Out-Null
        Write-Host "         +  $dir" -ForegroundColor DarkGray
    } else {
        Write-Skip "$dir ya existe."
    }
}
Write-OK "Directorios listos."

# --------------------------------------------------------------------------
# DOCKER COMPOSE UP
# --------------------------------------------------------------------------

Write-Header "LEVANTANDO CONTENEDORES"
Set-Location $ScriptDir

Write-Step "1" "2" "Ejecutando docker compose up -d..."
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Error al levantar los contenedores."
    Write-Host "  Revisa los logs: docker compose logs" -ForegroundColor Yellow
    exit 1
}
Write-OK "Contenedores iniciados."

# Esperar a que Evolution API responda (max 90 segundos)
Write-Step "2" "2" "Esperando que Evolution API este lista (max 90s)..."
$maxAttempts = 45
$attempt = 0
$ready = $false
while ($attempt -lt $maxAttempts -and -not $ready) {
    Start-Sleep -Seconds 2
    $attempt++
    try {
        $null = Invoke-RestMethod -Uri "http://localhost:8080/" -TimeoutSec 3 -ErrorAction Stop
        $ready = $true
    } catch {
        Write-Host "         ... $($attempt * 2)s / 90s" -ForegroundColor DarkGray
    }
}

if (-not $ready) {
    Write-Fail "Evolution API no respondio en 90 segundos."
    Write-Host "  Revisa: docker compose logs evolution --tail 50" -ForegroundColor Yellow
    exit 1
}
Write-OK "Evolution API lista en http://localhost:8080"

# --------------------------------------------------------------------------
# DEPENDENCIAS PYTHON + INSTANCIA / WEBHOOK
# --------------------------------------------------------------------------

Write-Header "CONFIGURANDO AGENTE PYTHON"
$AgentDir = Join-Path $ScriptDir "agent"
Set-Location $AgentDir

Write-Step "1" "2" "Instalando dependencias Python (requirements.txt)..."
pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Error instalando dependencias."
    exit 1
}
Write-OK "Dependencias instaladas."

Write-Step "2" "2" "Registrando instancia y webhook en Evolution API..."
$env:EVOLUTION_API_KEY = $EvolutionApiKey
python setup_webhook.py
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Error en setup_webhook.py."
    exit 1
}

# --------------------------------------------------------------------------
# RESUMEN FINAL
# --------------------------------------------------------------------------

Write-Header "TODO LISTO"

Write-Host "  Servicios corriendo:" -ForegroundColor Green
Write-Host "    PostgreSQL  ->  localhost:5432" -ForegroundColor White
Write-Host "    Redis       ->  localhost:6379" -ForegroundColor White
Write-Host "    Evolution   ->  http://localhost:8080" -ForegroundColor White
Write-Host "    Manager UI  ->  http://localhost:8080/manager" -ForegroundColor White
Write-Host ""
Write-Host "  PROXIMOS PASOS MANUALES:" -ForegroundColor Cyan
Write-Host "    1. Escanea el QR de WhatsApp  (ver SETUP.md, Paso 4)" -ForegroundColor Yellow
Write-Host "    2. Inicia el agente:" -ForegroundColor Yellow
Write-Host "       cd $AgentDir" -ForegroundColor White
Write-Host "       python main.py" -ForegroundColor White
Write-Host ""
Write-Host "  Guarda estos datos:" -ForegroundColor DarkGray
Write-Host "    Evolution API Key : $EvolutionApiKey" -ForegroundColor DarkGray
Write-Host "    Numeros activos   : $AllowedNumbers" -ForegroundColor DarkGray
Write-Host "    Puerto agente     : $AgentPort" -ForegroundColor DarkGray
Write-Host ""

# --------------------------------------------------------------------------
# ZIP PARA COMPARTIR (OPCIONAL)
# --------------------------------------------------------------------------

$createZip = Ask "Crear ZIP para compartir con el equipo? (S/N)" "N"
if ($createZip -ieq "S") {

    Write-Header "CREANDO ZIP"

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    $zipName = "solvy-bancosol-$(Get-Date -Format 'yyyy-MM-dd').zip"
    $zipPath = Join-Path $ScriptDir $zipName

    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
        Write-Skip "ZIP anterior eliminado."
    }

    $filesToInclude = @(
        "docker-compose.yml",
        "setup.ps1",
        "SETUP.md",
        "agent\agent.py",
        "agent\evolution_client.py",
        "agent\gate.py",
        "agent\kb.py",
        "agent\llm_client.py",
        "agent\main.py",
        "agent\setup_webhook.py",
        "agent\state_store.py",
        "agent\test_kb.py",
        "agent\requirements.txt",
        "agent\.env.example"
    )

    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
    foreach ($rel in $filesToInclude) {
        $full = Join-Path $ScriptDir $rel
        if (Test-Path $full) {
            $entry = $rel.Replace("\", "/")
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $full, $entry,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
            Write-Host "         +  $rel" -ForegroundColor DarkGray
        } else {
            Write-Skip "Omitido (no existe): $rel"
        }
    }
    $zip.Dispose()

    Write-OK "ZIP creado: $zipName"
    Write-Host ""
    Write-Host "  Compartilo junto con la carpeta del KB (Problemas\)." -ForegroundColor Yellow
    Write-Host "  El KB NO esta en el ZIP - cada maquina tiene su propia ruta." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Setup completo. Consulta SETUP.md para el resto del proceso." -ForegroundColor Cyan
Write-Host ""
