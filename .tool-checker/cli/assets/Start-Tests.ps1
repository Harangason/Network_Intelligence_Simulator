[CmdletBinding()]
param(
    [Parameter(Position=0)][ValidateSet('menu','start','help','plan','status','results','catalog','sources','export','migrate','run','prepare','preflight','markdown','prepare-project')][string]$Command = 'menu',
    [string]$Selection = 'on', [string]$Task, [string]$Inputs, [string]$Output, [string]$Source,
    [string]$PluginPath, [switch]$Reviewed,
    [ValidateRange(1,2147483647)][int]$Rounds = 1,
    [ValidateSet("continue","stop","pause")][string]$ErrorBehavior = "continue",
    [ValidateSet("verify","repair")][string]$Mode = "verify", [switch]$Interactive
)
$ErrorActionPreference = 'Stop'
# Windows PowerShell cannot load project runtimes that require PowerShell 7.
# Bound values are serialized as data, never interpolated as executable code.
if ($PSVersionTable.PSVersion.Major -lt 7) {
    try {
        $hostCommand = Get-Command pwsh -CommandType Application -ErrorAction SilentlyContinue
        $hostPath = if ($hostCommand) { $hostCommand.Source } else { Join-Path $env:ProgramFiles 'PowerShell/7/pwsh.exe' }
        if (!(Test-Path -LiteralPath $hostPath -PathType Leaf)) {
            throw 'PowerShell 7 (pwsh.exe) is required; installed host was not found'
        }
        if ((Get-Location).Provider.Name -ne 'FileSystem') { throw 'A filesystem working directory is required' }
        $forward = @{}
        foreach ($key in $PSBoundParameters.Keys) {
            $value = $PSBoundParameters[$key]
            if ($value -is [System.Management.Automation.SwitchParameter]) { $value = [bool]$value }
            $forward[$key] = $value
        }
        $payload = @{ script = $PSCommandPath; parameters = $forward; directory = (Get-Location).ProviderPath } | ConvertTo-Json -Depth 8 -Compress
        $data = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
        $wrapper = @'
$ErrorActionPreference = 'Stop'
try {
    if ($PSVersionTable.PSVersion.Major -lt 7) { throw 'Selected host is not PowerShell 7' }
    $payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PAYLOAD__')) | ConvertFrom-Json -AsHashtable
    Set-Location -LiteralPath $payload.directory
    $forward = $payload.parameters
    & $payload.script @forward
    exit $LASTEXITCODE
} catch {
    [Console]::Error.WriteLine('NOT_STARTED: PowerShell host bootstrap failed: ' + $_.Exception.Message)
    exit 70
}
'@
        $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrapper.Replace('__PAYLOAD__', $data)))
        if ($encoded.Length -gt 24000) { throw 'Bound parameters exceed the safe host bootstrap command length' }
        & $hostPath -NoProfile -EncodedCommand $encoded
        exit $LASTEXITCODE
    } catch {
        [Console]::Error.WriteLine('NOT_STARTED: PowerShell host bootstrap failed: ' + $_.Exception.Message)
        exit 70
    }
}

$artifacts = $PSScriptRoot
$settings = Get-Content -LiteralPath (Join-Path $artifacts "cli/project.json") -Raw | ConvertFrom-Json
$state = $settings.state
$project = $settings.project
$python = Join-Path $project '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$script = Join-Path $artifacts 'cli/scripts/standard_cli.py'
if ($Command -eq 'run' -or $Command -eq 'preflight') {
    $projectConfig = Join-Path $artifacts 'config/project-cli.json'
    if (Test-Path -LiteralPath $projectConfig) {
        $runtimeConfig = Get-Content -LiteralPath $projectConfig -Raw | ConvertFrom-Json
        if ($runtimeConfig.runtime_loader) {
            . $runtimeConfig.runtime_loader
            & $runtimeConfig.runtime_function -Names @($runtimeConfig.runtime_names) | Out-Null
        }
    }
}
$arguments = @($script, '--state', $state, $Command)
if ($Command -notin @('markdown','prepare-project')) { $arguments += @('--selection', $Selection) }
if ($Source) { $arguments += @('--source', $Source) }
if ($Task) { $arguments += @('--task', $Task) }
if ($Inputs) { $arguments += @('--inputs', $Inputs) }
if ($Output) { $arguments += @('--output', $Output) }
if ($PluginPath) { $arguments += @('--plugin-path', $PluginPath) }
if ($Reviewed) { $arguments += '--reviewed' }
$arguments += @('--rounds', [string]$Rounds, '--behavior', $ErrorBehavior, '--mode', $Mode)
if ($Interactive) { $arguments += '--interactive' }
$previousUtf8 = $env:PYTHONUTF8
try { $env:PYTHONUTF8 = '1'; & $python @arguments; $result = $LASTEXITCODE }
finally { $env:PYTHONUTF8 = $previousUtf8 }
exit $result
