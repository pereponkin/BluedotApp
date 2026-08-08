param(
  [Parameter(Position = 0)]
  [string]$Prompt = "",

  [int]$Limit = 10,

  [string]$Preset = "auto",

  [switch]$IncludeAdvanced,

  [switch]$NoAuto
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$Args = @("-m", "bluedot_agent.cli", "session", "--limit", "$Limit", "--preset", $Preset)
if ($Prompt) {
  $Args += $Prompt
}
if ($IncludeAdvanced) {
  $Args += "--include-advanced"
}
if ($NoAuto) {
  $Args += "--no-auto"
}

& $Python @Args
