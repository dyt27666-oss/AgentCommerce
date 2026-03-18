param(
  [double]$IntervalSec = 0.5,
  [int]$PageSize = 10,
  [string]$SourceArtifact = "artifacts/council_codex_dispatch_ready.json"
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

$appIdSet = -not [string]::IsNullOrWhiteSpace($env:AGENTCOMMERCE_FEISHU_APP_ID)
$appSecretSet = -not [string]::IsNullOrWhiteSpace($env:AGENTCOMMERCE_FEISHU_APP_SECRET)
$chatIdSet = -not [string]::IsNullOrWhiteSpace($env:AGENTCOMMERCE_FEISHU_CHAT_ID)
Write-Host ("[feishu-listener] env app_id_loaded=" + $appIdSet + " app_secret_loaded=" + $appSecretSet + " chat_id_loaded=" + $chatIdSet)

py -m tools.council_bridge.feishu_action_listener --max-polls 0 --interval-sec $IntervalSec --page-size $PageSize --source-artifact $SourceArtifact --action-stage auto
