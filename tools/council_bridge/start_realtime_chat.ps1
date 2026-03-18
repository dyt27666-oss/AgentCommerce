param(
  [double]$ListenerIntervalSec = 0.5,
  [double]$WorkerIntervalSec = 0.5,
  [int]$PageSize = 10,
  [string]$SourceArtifact = "artifacts/council_codex_dispatch_ready.json"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

$runtimeDir = Join-Path $repoRoot "artifacts\realtime"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$listenerPidPath = Join-Path $runtimeDir "feishu_listener.pid"
$workerPidPath = Join-Path $runtimeDir "bridge_worker.pid"

if ((Test-Path $listenerPidPath) -or (Test-Path $workerPidPath)) {
  Write-Host "[realtime-start] Existing pid files found. Run stop_realtime_chat.ps1 first if processes are still running."
}

$listenerStdout = Join-Path $runtimeDir "feishu_listener.stdout.log"
$listenerStderr = Join-Path $runtimeDir "feishu_listener.stderr.log"
$workerStdout = Join-Path $runtimeDir "bridge_worker.stdout.log"
$workerStderr = Join-Path $runtimeDir "bridge_worker.stderr.log"

$listenerScript = Join-Path $repoRoot "tools\council_bridge\run_feishu_listener_forever.ps1"
$workerScript = Join-Path $repoRoot "tools\council_bridge\run_bridge_worker_forever.ps1"

$listenerProc = Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  $listenerScript,
  "-IntervalSec",
  "$ListenerIntervalSec",
  "-PageSize",
  "$PageSize",
  "-SourceArtifact",
  "$SourceArtifact"
) -PassThru -WindowStyle Hidden -RedirectStandardOutput $listenerStdout -RedirectStandardError $listenerStderr

$workerProc = Start-Process -FilePath "powershell" -ArgumentList @(
  "-NoProfile",
  "-ExecutionPolicy",
  "Bypass",
  "-File",
  $workerScript,
  "-IntervalSec",
  "$WorkerIntervalSec"
) -PassThru -WindowStyle Hidden -RedirectStandardOutput $workerStdout -RedirectStandardError $workerStderr

$listenerProc.Id | Set-Content -Encoding ASCII $listenerPidPath
$workerProc.Id | Set-Content -Encoding ASCII $workerPidPath

Write-Host "[realtime-start] listener pid=$($listenerProc.Id)"
Write-Host "[realtime-start] worker pid=$($workerProc.Id)"
Write-Host "[realtime-start] logs: $runtimeDir"
