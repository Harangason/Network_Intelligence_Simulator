param(
    [Parameter(Mandatory = $true)]
    [string]$Model,
    [string]$Server = 'llama-server.exe',
    [ValidateRange(1, 65535)]
    [int]$Port = 18081,
    [ValidateRange(0, 999)]
    [int]$GpuLayers = 999
)

$ErrorActionPreference = 'Stop'
$modelPath = (Resolve-Path -LiteralPath $Model).ProviderPath
if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf) -or
    [IO.Path]::GetExtension($modelPath) -ne '.gguf') {
    throw "Expected a GGUF model file: $Model"
}
$serverPath = (Get-Command -Name $Server -CommandType Application).Source

& $serverPath -m $modelPath -c 20480 -ngl $GpuLayers -fa on --jinja `
    -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 4 `
    --reasoning-effort low --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
