# Local PM run (Windows): loads the plugin's .env (gitignored secrets) into
# this process, loads the plugin, and executes one /pm-run on your
# interactive claude login.
# Usage: .\AgenticProjectManager\bin\pm-local.ps1 [-Trigger manual] [-Focus "..."]

param(
    [string]$Trigger = "manual",
    [string]$Focus = ""
)

$PluginDir = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $PluginDir

$EnvFile = Join-Path $PluginDir ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        $line = $line.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $k, $v = $line.Split("=", 2)
            $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
            if ($k -and -not (Test-Path "Env:$k")) {
                Set-Item -Path "Env:$k" -Value $v
            }
        }
    }
}

$RunId = "pm-local-" + (Get-Date -Format "yyyyMMdd-HHmmss")
$Prompt = "/pm-run $Trigger $RunId"
if ($Focus) { $Prompt += " focus:$Focus" }

Set-Location $ProjectRoot
claude --plugin-dir $PluginDir $Prompt
