param([int]$ApiPort = 8000, [int]$WebPort = 3000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $projectRoot
$runtimeNode = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
if (!(Test-Path -LiteralPath $runtimeNode)) { $runtimeNode = (Get-Command node -ErrorAction Stop).Source }
$env:PATH = (Split-Path $runtimeNode -Parent) + ';' + $env:PATH
$nodeVersion = & $runtimeNode -p 'parseInt(process.versions.node)'
if ([int]$nodeVersion -lt 22) { throw 'Please install Node.js 22 or newer.' }
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { python -m venv .venv }
if (!(Test-Path -LiteralPath '.env')) {
    & $pythonExe -c "from pathlib import Path; import secrets; Path('.env').write_text('DATABASE_URL=sqlite:///./biology.db\nJWT_SECRET='+secrets.token_urlsafe(48)+'\n',encoding='utf-8')"
}
& $pythonExe -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed.' }
& $pythonExe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& $pythonExe scripts\seed.py
if ($LASTEXITCODE -ne 0) { throw 'Seed import failed.' }
New-Item -ItemType Directory -Force -Path tmp | Out-Null
$records = @()
if (!(Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue)) {
    $apiProcess = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot\tmp\api.log" -RedirectStandardError "$projectRoot\tmp\api-error.log"
    $records += @{id=$apiProcess.Id; path=$pythonExe; started=$apiProcess.StartTime.ToUniversalTime().ToString('o')}
}
Push-Location (Join-Path $projectRoot 'frontend')
try {
    if (!(Test-Path -LiteralPath 'node_modules\next\dist\bin\next')) {
        $npmCommand = Get-Command npm.cmd -ErrorAction Stop
        $npmCli = Join-Path (Split-Path $npmCommand.Source -Parent) 'node_modules\npm\bin\npm-cli.js'
        & $runtimeNode $npmCli ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependencies failed.' }
    }
    if (!(Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue)) {
        $env:NEXT_PUBLIC_API_URL = "http://localhost:$ApiPort/api/v1"
        $webProcess = Start-Process -FilePath $runtimeNode -ArgumentList @('node_modules/next/dist/bin/next','dev','--webpack','--hostname','127.0.0.1','--port',"$WebPort") -WorkingDirectory (Get-Location).Path -WindowStyle Hidden -PassThru -RedirectStandardOutput "$projectRoot\tmp\web.log" -RedirectStandardError "$projectRoot\tmp\web-error.log"
        $records += @{id=$webProcess.Id; path=$runtimeNode; started=$webProcess.StartTime.ToUniversalTime().ToString('o')}
    }
} finally { Pop-Location }
if ($records.Count) { @($records) | ConvertTo-Json | Set-Content -LiteralPath 'tmp\local-processes.json' -Encoding utf8 }
Write-Host "Web: http://localhost:$WebPort | API: http://localhost:$ApiPort/docs"
