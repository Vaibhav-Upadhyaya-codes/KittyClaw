# KittyClaw Installer for Windows PowerShell
# Install with: powershell -ExecutionPolicy Bypass -File install.ps1
# Or: iwr -useb https://raw.githubusercontent.com/your-repo/kittyclaw/main/install.ps1 | iex

param(
    [switch]$NoPrompt = $false
)

$ErrorActionPreference = "Stop"
$KittyDir = Join-Path $env:USERPROFILE ".kittyclaw"
$EnvFile = Join-Path $KittyDir ".env"

Write-Host "`n=== Kitty Claw Installer ===" -ForegroundColor Cyan
Write-Host "Installing Kitty Claw AI Code Assistant...`n"

# Create config directory
if (!(Test-Path $KittyDir)) {
    New-Item -ItemType Directory -Path $KittyDir -Force | Out-Null
}

# Check for existing installation
if (Test-Path $EnvFile) {
    Write-Host "Existing Kitty Claw configuration found at: $EnvFile" -ForegroundColor Yellow
    if (-not $NoPrompt) {
        $response = Read-Host "Do you want to reconfigure? (y/N)"
        if ($response -match '^[Yy]') {
            Remove-Item $EnvFile -Force
        } else {
            Write-Host "Installation complete! Run 'kittyclaw' to start." -ForegroundColor Green
            exit 0
        }
    }
}

# Check for Python
Write-Host "[1/4] Checking Python..." -ForegroundColor Cyan
$PythonCmd = "python"
try {
    $PythonVersion = & $PythonCmd --version 2>&1
    Write-Host "  Found: $PythonVersion" -ForegroundColor Green
} catch {
    $PythonCmd = "python3"
    try {
        $PythonVersion = & $PythonCmd --version 2>&1
        Write-Host "  Found: $PythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Python 3.8+ is required but not found!" -ForegroundColor Red
        Write-Host "  Please install Python from: https://python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
}

# Check for pip
Write-Host "[2/4] Checking pip..." -ForegroundColor Cyan
try {
    & $PythonCmd -m pip --version 2>&1 | Out-Null
    Write-Host "  pip is available" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: pip is not available" -ForegroundColor Red
    exit 1
}

# Install the package
Write-Host "[3/4] Installing kittyclaw package..." -ForegroundColor Cyan
try {
    & $PythonCmd -m pip install -e . --quiet 2>&1 | Out-Null
    Write-Host "  Package installed successfully" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Installation failed" -ForegroundColor Red
    Write-Host "  $_"
    exit 1
}

# Configure API key and check Ollama
Write-Host "[4/4] Configuring Kitty Claw..." -ForegroundColor Cyan

# Check for ollama
$OllamaPath = "ollama"
$OllamaInstalled = $false
try {
    & $OllamaPath --version 2>&1 | Out-Null
    $OllamaInstalled = $true
    Write-Host "  Ollama found: available" -ForegroundColor Green
} catch {
    Write-Host "  Ollama not found" -ForegroundColor Yellow
    if (-not $NoPrompt) {
        Write-Host "  Ollama is recommended for local AI models." -ForegroundColor Cyan
        Write-Host "  Download from: https://ollama.ai" -ForegroundColor Cyan
        Write-Host "  After installation, you can run 'ollama pull llama3' to get a model" -ForegroundColor Cyan
    }
}

# Get OpenRouter API key
Write-Host "`n=== Configuration ===" -ForegroundColor Cyan
$ApiKey = $env:OPENROUTER_API_KEY
if ([string]::IsNullOrEmpty($ApiKey)) {
    Write-Host "  OpenRouter API Key not found in environment." -ForegroundColor Yellow
    Write-Host "  Get one at: https://openrouter.ai/keys" -ForegroundColor Cyan
    if (-not $NoPrompt) {
        $ApiKey = Read-Host "  Enter your OpenRouter API key (or press Enter to skip)"
    }
}

if (-not [string]::IsNullOrEmpty($ApiKey)) {
    # Clean up API key
    $ApiKey = $ApiKey.Trim()
    if ($ApiKey -match '^sk-[a-zA-Z0-9]+$') {
        # Save to .env file
        $EnvContent = @"
# Kitty Claw Configuration
OPENROUTER_API_KEY=$ApiKey
OLLAMA_HOST=http://localhost:11434
"@
        $EnvContent | Out-File -FilePath $EnvFile -Encoding UTF8 -Force
        Write-Host "  Configuration saved to: $EnvFile" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: API key format looks invalid (should start with 'sk-')" -ForegroundColor Yellow
        Write-Host "  You can set it later by running: `$env:OPENROUTER_API_KEY = 'your-key'" -ForegroundColor Yellow
    }
} else {
    Write-Host "  No API key configured." -ForegroundColor Yellow
    Write-Host "  Set it with: `$env:OPENROUTER_API_KEY = 'your-key'" -ForegroundColor Yellow
    Write-Host "  Or edit: $EnvFile" -ForegroundColor Yellow
}

Write-Host "`n=== Installation Complete ===" -ForegroundColor Green
Write-Host "  Run 'kittyclaw' to launch Kitty Claw!" -ForegroundColor Green
Write-Host "  Configuration directory: $KittyDir" -ForegroundColor Cyan
Write-Host ""