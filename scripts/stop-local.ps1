$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$recordFile = Join-Path $projectRoot 'tmp\local-processes.json'
if (Test-Path -LiteralPath $recordFile) {
    foreach ($record in (Get-Content -Raw -LiteralPath $recordFile | ConvertFrom-Json)) {
        $serviceProcess = Get-Process -Id $record.id -ErrorAction SilentlyContinue
        if ($serviceProcess -and $serviceProcess.Path -eq $record.path -and $serviceProcess.StartTime.ToUniversalTime().ToString('o') -eq $record.started) {
            # Only the process recorded by this project's start script is stopped.
            Stop-Process -Id $serviceProcess.Id
        }
    }
    Remove-Item -LiteralPath $recordFile
}
