param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Prompt,

  [string]$Preset = "auto",

  [switch]$BasicOnly,

  [switch]$Detached,

  [int]$StartupWaitSeconds = 20
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StateDir = if ($env:BLUEDOT_STATE_DIR) { $env:BLUEDOT_STATE_DIR } else { Join-Path $env:LOCALAPPDATA "BlueDotAgent" }
$LogsDir = if ($env:BLUEDOT_LOG_DIR) { $env:BLUEDOT_LOG_DIR } else { Join-Path $StateDir "logs" }

$Args = @("-m", "bluedot_agent.cli", "playlist", "--prompt-env", "BLUEDOT_LAUNCH_PROMPT", "--preset", $Preset)
if ($BasicOnly) {
  $Args += "--basic-only"
}

if (-not $Detached) {
  $env:BLUEDOT_LAUNCH_PROMPT = $Prompt
  try {
    & $Python @Args
    $ExitCode = $LASTEXITCODE
  } finally {
    Remove-Item Env:BLUEDOT_LAUNCH_PROMPT -ErrorAction SilentlyContinue
  }
  exit $ExitCode
}

New-Item -ItemType Directory -Force $LogsDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Stdout = Join-Path $LogsDir "playlist_live_$Timestamp.out.log"
$Stderr = Join-Path $LogsDir "playlist_live_$Timestamp.err.log"
$env:BLUEDOT_LAUNCH_PROMPT = $Prompt
try {
  $Process = Start-Process `
    -FilePath $Python `
    -WorkingDirectory $ProjectRoot `
    -ArgumentList $Args `
    -RedirectStandardOutput $Stdout `
    -RedirectStandardError $Stderr `
    -WindowStyle Hidden `
    -PassThru
} finally {
  Remove-Item Env:BLUEDOT_LAUNCH_PROMPT -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds ([Math]::Min(2, $StartupWaitSeconds))
$Process.Refresh()
$Ready = -not $Process.HasExited

Write-Host "Blue Dot playlist agent PID: $($Process.Id)"
Write-Host "stdout: $Stdout"
Write-Host "stderr: $Stderr"

if (-not $Ready) {
  if (-not $Process.HasExited) {
    Write-Host "Agent is still starting; inspect the logs before starting another copy."
    exit 3
  }
  Write-Host "Agent exited during startup with code $($Process.ExitCode)."
  if (Test-Path $Stdout) {
    Get-Content $Stdout -Tail 40
  }
  if (Test-Path $Stderr) {
    Get-Content $Stderr -Tail 80
  }
  exit $Process.ExitCode
}

Write-Host "Agent browser is ready. Close its window when you are done."
