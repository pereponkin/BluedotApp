param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Prompt,
  [int]$Limit = 10,
  [string]$Preset = "auto",
  [switch]$BasicOnly,
  [switch]$Close,
  [switch]$Headless,
  [switch]$Json
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

$Args = @("-m", "bluedot_agent.cli", "api-search", $Prompt, "--preset", $Preset, "--limit", "$Limit")
if ($BasicOnly) {
  $Args += "--basic-only"
}
if ($Close) {
  $Args += "--close"
}
if ($Headless) {
  $Args += "--headless"
}
if ($Json) {
  $Args += "--json"
}

& $Python @Args
