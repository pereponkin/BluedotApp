param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Prompt,

  [int]$Limit = 10,

  [string]$Preset = "auto",

  [switch]$Auto,

  [switch]$KeepOpen,

  [switch]$IncludeAdvanced,

  [switch]$DryRun,

  [switch]$DebugDom,

  [switch]$Json
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$Args = @("-m", "bluedot_agent.cli", "search", $Prompt, "--limit", "$Limit", "--preset", $Preset)
if ($Auto) {
  $Args += "--auto"
}
if ($KeepOpen) {
  $Args += "--keep-open"
}
if ($IncludeAdvanced) {
  $Args += "--include-advanced"
}
if ($DryRun) {
  $Args += "--dry-run"
}
if ($DebugDom) {
  $Args += "--debug-dom"
}
if ($Json) {
  $Args += "--json"
}

& $Python @Args
