$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { throw 'Backend virtual environment missing. See RUNNING.md for one-time setup.' }
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) { throw 'Frontend packages missing. See RUNNING.md for one-time setup.' }
Push-Location $backend
try { & $python -m alembic upgrade head; if ($LASTEXITCODE -ne 0) { throw 'Migration failed.' } }
finally { Pop-Location }
try {
  $apiReady = (Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
  $webReady = (Invoke-WebRequest 'http://127.0.0.1:5173/clarity' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
  if ($apiReady -and $webReady) {
    try { $stage4Ready = (Invoke-WebRequest 'http://127.0.0.1:8000/api/integrations/google/status' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { $stage4Ready = $false }
    if ($stage4Ready) { Write-Host 'Aniro already running: http://127.0.0.1:5173/plan'; exit 0 }
    throw 'An older Aniro API is using port 8000. Stop that API process and rerun start.ps1.'
  }
} catch {}
if ($apiReady -and $webReady -and -not $stage4Ready) { throw 'An older Aniro API is using port 8000. Stop that API process and rerun start.ps1.' }
$api = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $backend -WindowStyle Hidden -PassThru
$web = Start-Process -FilePath 'npm.cmd' -ArgumentList @('run','dev') -WorkingDirectory $frontend -WindowStyle Hidden -PassThru
for ($attempt = 0; $attempt -lt 40; $attempt++) {
  Start-Sleep -Milliseconds 500
  try {
    $apiReady = (Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    $webReady = (Invoke-WebRequest 'http://127.0.0.1:5173/clarity' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    $stage4Ready = (Invoke-WebRequest 'http://127.0.0.1:8000/api/integrations/google/status' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200
    if ($apiReady -and $webReady -and $stage4Ready) { Write-Host 'Aniro ready: http://127.0.0.1:5173/plan'; Write-Host "API PID: $($api.Id); web PID: $($web.Id)"; exit 0 }
  } catch {}
}
throw 'Servers did not become ready. Check whether ports 8000 and 5173 are free.'
