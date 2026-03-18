param(
    [Parameter(Mandatory = $true)]
    [string]$TagName,

    [string]$TagMessage = "",

    [switch]$PushTag
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[checkpoint] $Message"
}

Write-Step "verify git repository"
git rev-parse --is-inside-work-tree | Out-Null

Write-Step "verify working tree is clean"
$status = git status --porcelain
if ($status) {
    Write-Error "Working tree is not clean. Please commit or stash changes before creating stable checkpoint tag."
}

Write-Step "verify tag does not already exist"
$existing = git tag --list $TagName
if ($existing) {
    Write-Error "Tag '$TagName' already exists."
}

$headCommit = (git rev-parse --short HEAD).Trim()
$currentBranch = (git branch --show-current).Trim()
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

if ([string]::IsNullOrWhiteSpace($TagMessage)) {
    $TagMessage = "Stable checkpoint on $currentBranch @ $headCommit ($timestamp)"
}

Write-Step "create annotated tag $TagName at $headCommit"
git tag -a $TagName -m $TagMessage

Write-Step "tag created successfully"
git show $TagName --no-patch

if ($PushTag) {
    Write-Step "push tag to origin"
    git push origin $TagName
}

