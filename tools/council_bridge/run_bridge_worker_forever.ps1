param(
  [double]$IntervalSec = 0.5
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    $line = [string]$_
    if (-not $line) { return }
    $line = $line.Trim()
    if (-not $line) { return }
    if ($line.StartsWith("#")) { return }
    if ($line.StartsWith("export ")) {
      $line = $line.Substring(7).Trim()
    }
    if ($line -match '^[A-Za-z_][A-Za-z0-9_]*\s*=') {
      $k, $v = $line -split '=', 2
      $k = $k.Trim().TrimStart([char]0xFEFF)
      $v = $v.Trim()
      if (
        ($v.StartsWith('"') -and $v.EndsWith('"')) -or
        ($v.StartsWith("'") -and $v.EndsWith("'"))
      ) {
        $v = $v.Substring(1, $v.Length - 2)
      }
      [Environment]::SetEnvironmentVariable($k, $v, 'Process')
    }
  }
}

$webhookSet = -not [string]::IsNullOrWhiteSpace($env:AGENTCOMMERCE_FEISHU_WEBHOOK_URL)
Write-Host ("[bridge-worker] env webhook_loaded=" + $webhookSet)

py -m tools.council_bridge.bridge_worker --loop --interval-sec $IntervalSec --max-iterations 0
