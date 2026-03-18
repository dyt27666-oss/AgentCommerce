$ErrorActionPreference = "Continue"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$runtimeDir = Join-Path $repoRoot "artifacts\realtime"

$pidFiles = @(
  (Join-Path $runtimeDir "feishu_listener.pid"),
  (Join-Path $runtimeDir "bridge_worker.pid")
)

foreach ($pidFile in $pidFiles) {
  if (-not (Test-Path $pidFile)) {
    continue
  }
  $pidText = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
  $pidValue = 0
  [void][int]::TryParse([string]$pidText, [ref]$pidValue)
  if ($pidValue -gt 0) {
    try {
      Stop-Process -Id $pidValue -Force -ErrorAction Stop
      Write-Host "[realtime-stop] stopped pid=$pidValue"
    } catch {
      Write-Host "[realtime-stop] pid=$pidValue not running or cannot stop"
    }
  }
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "[realtime-stop] done"
