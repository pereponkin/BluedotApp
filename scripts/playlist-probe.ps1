param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Prompt,

  [string]$Preset = "auto",

  [int]$Seconds = 20,

  [switch]$BasicOnly
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$Args = @("-m", "bluedot_agent.cli", "playlist-probe", $Prompt, "--preset", $Preset, "--seconds", "$Seconds")
if ($BasicOnly) {
  $Args += "--basic-only"
}

& $Python @Args
