<#
  ConsultMeet - one-shot Windows setup.

  Run from an ADMINISTRATOR PowerShell (or just double-click run_setup.bat,
  which elevates automatically), from inside the consultmeet folder:

      powershell -ExecutionPolicy Bypass -File setup.ps1

  What this does:
    1. Installs MySQL Server via Chocolatey, if it isn't installed yet
    2. Starts the MySQL Windows service
    3. Figures out (or asks for) the root password, then sets it to one
       this script controls and writes to .env
    4. Creates the `consultmeet` database
    5. Creates a Python virtual environment and installs dependencies
    6. Creates the database tables
    7. Launches the app at http://localhost:5000

  NOTE: installing a database server unattended is one of the few things
  Windows doesn't make fully predictable across machines. This script
  automates every step it safely can and will only stop to ask you
  something if it truly can't figure it out on its own (almost always:
  "what's MySQL's current root password?").
#>

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "    $msg" -ForegroundColor Red }

# ---------- 0. Require admin ----------
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Err "Please re-run this as Administrator (or double-click run_setup.bat, which does this for you)."
    exit 1
}

function Test-CommandExists($cmd) { return $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }

# ---------- 1. Chocolatey ----------
Write-Step "Checking for Chocolatey (used to install MySQL unattended)"
if (-not (Test-CommandExists choco)) {
    Write-Warn "Chocolatey not found. Installing it..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    $env:Path += ";$env:ProgramData\chocolatey\bin"
}
Write-Ok "Chocolatey ready."

# ---------- 2. MySQL Server ----------
Write-Step "Checking for MySQL Server"
$mysqlService = Get-Service -Name "*mysql*" -ErrorAction SilentlyContinue

$initialPassword = $null
$freshInstall = $false

if (-not $mysqlService) {
    Write-Warn "MySQL not found. Installing via Chocolatey (this can take a few minutes)..."
    $freshInstall = $true
    choco install mysql -y --no-progress | Tee-Object -Variable chocoOutput
    Start-Sleep -Seconds 8
    $mysqlService = Get-Service -Name "*mysql*" -ErrorAction SilentlyContinue

    # The Chocolatey mysql package sometimes prints a generated root password,
    # or leaves it blank. Try to spot a generated password in its output.
    $passwordLine = $chocoOutput | Select-String -Pattern "password" -SimpleMatch | Select-Object -First 1
    if ($passwordLine -match "([A-Za-z0-9!@#$%^&*_\-]{8,})\s*$") {
        $initialPassword = $Matches[1]
        Write-Ok "Detected a generated initial root password from the installer output."
    }
}

if (-not $mysqlService) {
    Write-Err "MySQL still isn't installed. Install it manually from https://dev.mysql.com/downloads/installer/ then re-run this script."
    exit 1
}

if ($mysqlService.Status -ne 'Running') {
    Write-Step "Starting MySQL service ($($mysqlService.Name))"
    Start-Service $mysqlService.Name
    Start-Sleep -Seconds 5
}
Write-Ok "MySQL service '$($mysqlService.Name)' is running."

# ---------- 3. Locate mysql.exe ----------
Write-Step "Locating mysql.exe"
$mysqlExe = Get-ChildItem -Path "C:\Program Files\MySQL", "C:\ProgramData\chocolatey\lib" -Recurse -Filter "mysql.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $mysqlExe) {
    Write-Err "Couldn't find mysql.exe automatically. You'll need to create the database and set the password manually (see README.md), then re-run this script."
    exit 1
}
Write-Ok "Found: $($mysqlExe.FullName)"

# ---------- 4. Decide on a root password ----------
# We'll standardize on a password this script generates (or one you already know),
# then write it to .env so the app can connect.
$newPassword = [guid]::NewGuid().ToString("N").Substring(0,16)

function Try-MySqlNoPassword {
    & $mysqlExe.FullName -u root -e "SELECT 1;" 2>$null
    return $LASTEXITCODE -eq 0
}

function Try-MySqlWithPassword($pwd) {
    & $mysqlExe.FullName -u root "-p$pwd" -e "SELECT 1;" 2>$null
    return $LASTEXITCODE -eq 0
}

Write-Step "Configuring the MySQL root password"
$connected = $false
$currentPassword = $null

if ($freshInstall -and $initialPassword -and (Try-MySqlWithPassword $initialPassword)) {
    $currentPassword = $initialPassword
    $connected = $true
    Write-Ok "Logged in using the password detected from the installer."
} elseif (Try-MySqlNoPassword) {
    $currentPassword = ""
    $connected = $true
    Write-Ok "Logged in with a blank root password (default for a fresh install)."
}

if (-not $connected) {
    Write-Warn "Couldn't determine MySQL's current root password automatically."
    $secure = Read-Host "Enter the CURRENT MySQL root password" -AsSecureString
    $currentPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if (-not (Try-MySqlWithPassword $currentPassword)) {
        Write-Err "That password didn't work either. Please fix MySQL access manually, then re-run this script."
        exit 1
    }
}

# Set the password to our generated one, so future runs of this script are fully unattended.
if ($currentPassword -eq "") {
    & $mysqlExe.FullName -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$newPassword'; FLUSH PRIVILEGES;"
} else {
    & $mysqlExe.FullName -u root "-p$currentPassword" -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$newPassword'; FLUSH PRIVILEGES;"
}
Write-Ok "Root password set."

# ---------- 5. Create the database ----------
Write-Step "Creating the 'consultmeet' database"
& $mysqlExe.FullName -u root "-p$newPassword" -e "CREATE DATABASE IF NOT EXISTS consultmeet CHARACTER SET utf8mb4;"
Write-Ok "Database ready."

# ---------- 6. Python venv + dependencies ----------
Write-Step "Setting up the Python virtual environment"
if (-not (Test-CommandExists python)) {
    Write-Err "Python isn't installed or isn't on PATH. Install it from https://python.org (check 'Add to PATH' during install), then re-run this script."
    exit 1
}
if (-not (Test-Path ".\venv")) {
    python -m venv venv
}
Write-Ok "Virtual environment ready."

Write-Step "Installing Python dependencies"
.\venv\Scripts\pip.exe install -q -r requirements.txt
Write-Ok "Dependencies installed."

# ---------- 7. Write .env ----------
Write-Step "Writing .env"
@"
SECRET_KEY=$([guid]::NewGuid().ToString("N"))
DB_ENGINE=mysql
MYSQL_USER=root
MYSQL_PASSWORD=$newPassword
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=consultmeet
"@ | Out-File -FilePath ".env" -Encoding utf8 -Force
Write-Ok ".env written."

# ---------- 8. Create tables ----------
Write-Step "Creating database tables"
.\venv\Scripts\flask.exe --app app init-db
Write-Ok "Tables created."

# ---------- 9. Launch ----------
Write-Step "Setup complete! Starting ConsultMeet..."
Write-Host "`nVisit http://localhost:5000 in your browser. Press Ctrl+C here to stop the server.`n" -ForegroundColor Green
.\venv\Scripts\python.exe app.py
