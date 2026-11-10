param([Parameter(Mandatory=$true)][string]$WindowId)
$ErrorActionPreference='Stop'
if($WindowId -notmatch '^nis-eip-existing-only-20261109-r\d\d$'){throw 'Unexpected window identity'}
$taskProcesses=@(Get-CimInstance Win32_Process)
$taskMain=@($taskProcesses | Where-Object {$_.ProcessId -eq 72512 -and $_.Name -eq 'ollama.exe'})
if($taskMain.Count -ne 1){throw 'Main provider identity changed'}
$taskIds=[System.Collections.Generic.HashSet[int]]::new()
foreach($taskProcess in $taskProcesses){
    if($taskProcess.ProcessId -eq 72512 -or $taskProcess.ExecutablePath -like 'I:\PycharmProjects\My_first_Network_Simulator\*' -or $taskProcess.CommandLine -like '*I:\PycharmProjects\My_first_Network_Simulator\*'){
        [void]$taskIds.Add([int]$taskProcess.ProcessId)
    }
}
$taskAdded=$true
while($taskAdded){
    $taskAdded=$false
    foreach($taskProcess in $taskProcesses){
        if($taskIds.Contains([int]$taskProcess.ParentProcessId) -and $taskIds.Add([int]$taskProcess.ProcessId)){$taskAdded=$true}
    }
}
# Preserve every owned local endpoint. Do not filter unknown/undecoded TCP State.
$taskRows=@(Get-NetTCPConnection | Where-Object {$taskIds.Contains([int]$_.OwningProcess)} | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess,State)
$taskUdp=@(Get-NetUDPEndpoint | Where-Object {$taskIds.Contains([int]$_.OwningProcess)} | Select-Object LocalAddress,LocalPort,OwningProcess)
$taskWorkers=@($taskProcesses | Where-Object {$_.ParentProcessId -eq 72512 -and $_.Name -eq 'llama-server.exe'})
$taskModels=Invoke-RestMethod http://127.0.0.1:11434/api/ps
if($taskWorkers.Count -eq 0 -and @($taskModels.models).Count -ne 0){throw 'Loaded model without observed worker'}
foreach($taskWorker in $taskWorkers){
    $taskWorkerPort=[int]([regex]::Match($taskWorker.CommandLine,'--port\s+(\d+)').Groups[1].Value)
    if(-not @($taskRows | Where-Object {$_.LocalPort -eq $taskWorkerPort -and $_.OwningProcess -eq $taskWorker.ProcessId})){throw 'Missing actual worker endpoint'}
}
if(-not @($taskRows | Where-Object {$_.LocalPort -eq 11434 -and $_.OwningProcess -eq 72512})){throw 'Missing actual main provider endpoint'}
$taskDocker='C:/Users/marti/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe'
$taskNames=@(& $taskDocker ps --format '{{.Names}}' | Where-Object {$_ -match '^(NetworkIS|nis-)'})
$taskContainers=@(foreach($taskName in $taskNames){
    $taskContainer=(& $taskDocker inspect $taskName | ConvertFrom-Json)[0]
    [pscustomobject]@{name=$taskName;image=$taskContainer.Image;state=$taskContainer.State.Status;health=$taskContainer.State.Health.Status;ports=$taskContainer.NetworkSettings.Ports}
})
$taskProduct=@($taskContainers | Where-Object {$_.name -eq 'NetworkIS'})
if($taskProduct.Count -ne 1 -or $taskProduct[0].image -ne 'sha256:c7edda158398ce6c13b5563f56df70575aa61345539fbc23a5aeb847164fca33' -or $taskProduct[0].health -ne 'healthy'){throw 'Production identity/health changed'}
$taskPorts=@(11434,13500,13502,13503,15050,18081,53625,64439)+@($taskRows.LocalPort)+@($taskUdp.LocalPort)
foreach($taskContainer in $taskContainers){foreach($taskProperty in $taskContainer.ports.PSObject.Properties){foreach($taskBinding in @($taskProperty.Value)){if($taskBinding.HostPort){$taskPorts+=[int]$taskBinding.HostPort}}}}
$taskReady=Invoke-RestMethod http://127.0.0.1:13500/api/ready
if($taskReady.status -ne 'ready'){throw 'Production not ready'}
$taskCaptured=[DateTime]::UtcNow
$taskReport=[ordered]@{approvalId=$WindowId;protectedPortsCapturedAtUtc=$taskCaptured.ToString('o');windowStartUtc=$taskCaptured.ToString('o');windowEndUtc=$taskCaptured.AddMinutes(15).ToString('o');dispatchBeforeUtc=$taskCaptured.AddSeconds(120).ToString('o');protectedPorts=@($taskPorts | Where-Object {$_} | Sort-Object -Unique);complete=$true;tcp=$taskRows;udp=$taskUdp;mainWorkers=@($taskWorkers | Select-Object ProcessId,ParentProcessId,CommandLine);models=$taskModels;containers=$taskContainers;productionReady=$taskReady;nativeRequest='NONE';regressionSession=52420;observation='All owned local IPv4/IPv6 TCP and UDP endpoints without State filtering plus Docker bindings; unknown states protected. Main provider and loaded worker ports independently positively checked.';scope='Exactly one pinned EIP Existing-only restart; no model dispatch/shared lifecycle/NIS changes'}
$taskDestination=Join-Path $PSScriptRoot ($WindowId+'-go.json')
if(Test-Path -LiteralPath $taskDestination){throw 'Never overwrite existing window'}
[IO.File]::WriteAllText($taskDestination,($taskReport | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
[pscustomobject]$taskReport | Select-Object approvalId,protectedPortsCapturedAtUtc,windowStartUtc,windowEndUtc,dispatchBeforeUtc,protectedPorts,complete,models | ConvertTo-Json -Depth 4
