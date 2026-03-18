param(
    [string]$StableTagPattern = "stable/*",
    [switch]$RequireCleanTree = $true,
    [switch]$RequireUpToDateWithOrigin = $true
)

$ErrorActionPreference = "Stop"
$script:HasFailure = $false

function Write-Check {
    param(
        [ValidateSet("PASS", "WARN", "FAIL")]
        [string]$Level,
        [string]$Message
    )
    switch ($Level) {
        "PASS" { Write-Host "[PASS] $Message" -ForegroundColor Green }
        "WARN" { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
        "FAIL" {
            Write-Host "[FAIL] $Message" -ForegroundColor Red
            $script:HasFailure = $true
        }
    }
}

git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Current directory is not a git repository."
}

$branch = (git branch --show-current).Trim()
$head = (git rev-parse --short HEAD).Trim()
Write-Host "=== AgentCommerce Pre-Demo Git Check ==="
Write-Host "Branch: $branch"
Write-Host "HEAD:   $head"

$statusShort = git status --short
if ($RequireCleanTree) {
    if ([string]::IsNullOrWhiteSpace(($statusShort -join ""))) {
        Write-Check "PASS" "Working tree is clean."
    } else {
        Write-Check "FAIL" "Working tree is not clean. Commit/stash required before demo."
    }
} elseif (-not [string]::IsNullOrWhiteSpace(($statusShort -join ""))) {
    Write-Check "WARN" "Working tree has local modifications."
}

$upstream = (git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($upstream)) {
    Write-Check "WARN" "No upstream configured for current branch."
} else {
    $aheadBehindRaw = (git rev-list --left-right --count "$upstream...HEAD").Trim()
    $aheadBehind = $aheadBehindRaw -split "\s+"
    $behind = [int]$aheadBehind[0]
    $ahead = [int]$aheadBehind[1]

    if ($RequireUpToDateWithOrigin -and ($ahead -ne 0 -or $behind -ne 0)) {
        Write-Check "FAIL" "Branch is not synced with $upstream (ahead=$ahead, behind=$behind)."
    } elseif ($ahead -eq 0 -and $behind -eq 0) {
        Write-Check "PASS" "Branch is synced with $upstream."
    } else {
        Write-Check "WARN" "Branch differs from $upstream (ahead=$ahead, behind=$behind)."
    }
}

$stableTags = @(git tag --list $StableTagPattern)
if ($stableTags.Count -eq 0) {
    Write-Check "FAIL" "No stable tag found with pattern '$StableTagPattern'."
} else {
    Write-Check "PASS" "Found $($stableTags.Count) stable tag(s)."
    $latestStable = (git for-each-ref --sort=-creatordate --format="%(refname:short)" "refs/tags/$StableTagPattern" | Select-Object -First 1).Trim()
    if (-not [string]::IsNullOrWhiteSpace($latestStable)) {
        Write-Host "Latest stable tag: $latestStable"
        git merge-base --is-ancestor $latestStable HEAD *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Check "PASS" "HEAD contains latest stable tag history."
        } else {
            Write-Check "WARN" "HEAD does not contain latest stable tag history."
        }
    }
}

if ($script:HasFailure) {
    Write-Host ""
    Write-Host "Result: FAIL (not demo-ready for strict git baseline)." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Result: PASS/WARN only (git baseline acceptable)." -ForegroundColor Green
exit 0
