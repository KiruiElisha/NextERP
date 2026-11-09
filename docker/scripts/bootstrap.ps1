# Create the local site (once) and install erpnext + nexterp.
# Run from the docker/ folder after `docker compose up -d`.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path .env) {
  Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $k, $v = $_ -split '=', 2
    if ($k -and $v) { Set-Item -Path "Env:$($k.Trim())" -Value $v.Trim() }
  }
}

$Site = if ($env:SITE_NAME) { $env:SITE_NAME } else { "localhost" }
$AdminPassword = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "admin" }
$DbPassword = if ($env:MYSQL_ROOT_PASSWORD) { $env:MYSQL_ROOT_PASSWORD } else { "admin" }
$Port = if ($env:HTTP_PORT) { $env:HTTP_PORT } else { "8000" }

Write-Host "Local ERPNext bootstrap (ERPNext v16 + nexterp)"
Write-Host "Waiting for backend…"
$ready = $false
1..60 | ForEach-Object {
  docker compose exec -T backend bench --version 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; return }
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  Write-Error "Backend is not ready. Run: docker compose up -d"
}

docker compose exec -T backend bash -c 'ls -1 apps > sites/apps.txt'

docker compose exec -T backend test -f "sites/$Site/site_config.json" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Creating site $Site…"
  docker compose exec -T backend bench new-site $Site `
    --mariadb-root-password $DbPassword `
    --admin-password $AdminPassword `
    --no-mariadb-socket `
    --install-app erpnext
} else {
  Write-Host "Site $Site already exists."
}

Write-Host "Installing nexterp…"
docker compose exec -T backend bench --site $Site install-app nexterp
if ($LASTEXITCODE -ne 0) {
  Write-Host "(install-app returned non-zero — app may already be installed)"
}

docker compose exec -T backend bench --site $Site set-config host_name "http://localhost:$Port"
docker compose exec -T backend bench use $Site

Write-Host ""
Write-Host "Local ERPNext is ready."
Write-Host "  URL:      http://localhost:$Port"
Write-Host "  User:     Administrator"
Write-Host "  Password: $AdminPassword"
Write-Host ""
Write-Host "In the desktop app, sign in with site address: http://localhost:$Port"
Write-Host "Cloud sync/backup stays separate — back up with:"
Write-Host "  docker compose exec backend bench --site $Site backup --with-files"
