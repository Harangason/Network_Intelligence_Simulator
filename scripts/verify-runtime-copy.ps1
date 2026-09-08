param(
    [string]$Source = 'I:\PycharmProjects\My_first_Network_Simulator\backend\runtime',
    [string]$Volume = 'networkis-runtime-data',
    [string]$Docker = 'C:\Users\marti\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe'
)
$ErrorActionPreference = 'Stop'
$folders = @('jobs', 'traces', 'ml_registry', 'agent-learning', 'agent-diagnostics', 'program-cache', 'service-logs', 'samples')
$sourceRoot = (Resolve-Path -LiteralPath $Source).Path
$expected = @{}
foreach ($folder in $folders) {
    foreach ($file in Get-ChildItem -LiteralPath (Join-Path $sourceRoot $folder) -Recurse -File) {
        $relative = [IO.Path]::GetRelativePath($sourceRoot, $file.FullName).Replace('\', '/')
        $expected[$relative] = [long]$file.Length
    }
}
$image = (& $Docker inspect NetworkIS --format '{{.Image}}' | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Simulator image could not be resolved.' }
$manifestProgram = 'import json,pathlib; r=pathlib.Path("/runtime"); print(json.dumps({str(p.relative_to(r)):p.stat().st_size for p in r.rglob("*") if p.is_file()}))'
$manifest = & $Docker run --rm -v "${Volume}:/runtime:ro" --entrypoint python $image -c $manifestProgram | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Could not read copied runtime volume.' }
$actual = $manifest | ConvertFrom-Json -AsHashtable
$differences = @()
foreach ($name in $expected.Keys) {
    if (-not $actual.ContainsKey($name) -or [long]$actual[$name] -ne $expected[$name]) { $differences += $name }
}
if ($differences.Count) { throw "Copy is incomplete: $($differences.Count) missing/different files: $($differences[0..([Math]::Min(5,$differences.Count-1))] -join ', ')" }
# The gzip/tar transport validates stream integrity. Also compare independent
# SHA-256 samples across trace directories and all small persisted registries.
$sample = @('jobs/registry.json')
$traceFiles = @($expected.Keys | Where-Object { $_ -like 'traces/*/simulation_result.json' } | Sort-Object)
if ($traceFiles.Count) {
    $stride = [Math]::Max(1, [int]($traceFiles.Count / 12))
    for ($i = 0; $i -lt $traceFiles.Count; $i += $stride) { $sample += $traceFiles[$i] }
}
$sampleJson = ConvertTo-Json -InputObject $sample -Compress
$hashProgram = 'import json,pathlib,hashlib,sys; r=pathlib.Path("/runtime"); print(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in json.loads(sys.argv[1])}))'
$hashes = & $Docker run --rm -v "${Volume}:/runtime:ro" --entrypoint python $image -c $hashProgram $sampleJson | Out-String
if ($LASTEXITCODE -ne 0) { throw 'Copy checksum verification failed.' }
$copiedHashes = $hashes | ConvertFrom-Json -AsHashtable
foreach ($name in $sample) {
    $hash = (Get-FileHash -LiteralPath (Join-Path $sourceRoot $name) -Algorithm SHA256).Hash
    if ($hash -ne $copiedHashes[$name]) { throw "Checksum mismatch: $name" }
}
[pscustomobject]@{ Verified = $true; Files = $expected.Count; Bytes = ($expected.Values | Measure-Object -Sum).Sum;
    ChecksumSamples = $sample.Count; SourcePreserved = $true; Volume = $Volume } | ConvertTo-Json
