param(
  [Parameter(Position = 0)]
  [string]$Prompt,

  [string]$Preset = "auto",

  [int]$Seconds = 60,

  [switch]$Manual,

  [switch]$ViaReact,

  [switch]$IncludeAdvanced
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Args = @("-m", "bluedot_agent.cli", "state-probe", "--preset", $Preset, "--seconds", "$Seconds")

if ($Prompt) {
  $Args += $Prompt
}
if ($Manual) {
  $Args += "--manual"
}
if ($ViaReact) {
  $Args += "--via-react"
}
if ($IncludeAdvanced) {
  $Args += "--include-advanced"
}

& $Python @Args
