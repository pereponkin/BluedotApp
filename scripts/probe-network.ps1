param(
  [int]$Seconds = 120,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$Args = @("-m", "bluedot_agent.cli", "probe-network", "--seconds", "$Seconds")
if ($Json) {
  $Args += "--json"
}

& $Python @Args
