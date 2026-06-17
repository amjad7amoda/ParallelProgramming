param(
    [Parameter(Mandatory = $true)]
    [string]$HostUrl,

    [Parameter(Mandatory = $true)]
    [string]$Label,

    [string]$LocustFile = 'locustfile_simple.py',
    [int]$Users = 100,
    [int]$SpawnRate = 10,
    [string]$RunTime = '5m',
    [string]$ResultsFile = 'benchmark_results.txt',
    [string]$MetricsFile = 'resource_usage.csv',
    [string]$ComposeFile,
    [string[]]$Services = @('db', 'web1', 'web2', 'web3', 'nginx'),
    [string[]]$ProcessNames = @('python', 'pythonw')
)

$resultsPath = Join-Path $PSScriptRoot $ResultsFile
$metricsPath = Join-Path $PSScriptRoot $MetricsFile
$locustPath = Join-Path $PSScriptRoot $LocustFile

$header = @"

$Label
$('-' * $Label.Length)
Date: $(Get-Date -Format o)
Host: $HostUrl
Users: $Users
Spawn rate: $SpawnRate
Run time: $RunTime
"@

Add-Content -Path $resultsPath -Value $header

if (Test-Path $metricsPath) {
    Add-Content -Path $metricsPath -Value "`n$Label`n$(('-' * $Label.Length))`nTimestamp,Container,CPU,Memory"
}
else {
    Add-Content -Path $metricsPath -Value "Label,Timestamp,Container,CPU,Memory"
}

$containerIds = @()
if ($ComposeFile) {
    foreach ($service in $Services) {
        $containerId = & docker compose -f $ComposeFile ps -q $service 2>$null
        if ($containerId) {
            $containerIds += $containerId.Trim()
        }
    }
}

$metricsJob = $null
if ($containerIds.Count -gt 0) {
    $metricsJob = Start-Job -ArgumentList @($containerIds, $metricsPath, $Label) -ScriptBlock {
        param($ids, $path, $scenarioLabel)
        while ($true) {
            $timestamp = Get-Date -Format o
            foreach ($id in $ids) {
                $line = & docker stats --no-stream --format "{{.Name}},{{.CPUPerc}},{{.MemUsage}}" $id 2>$null
                if ($line) {
                    Add-Content -Path $path -Value "$scenarioLabel,$timestamp,$line"
                }
            }
            Start-Sleep -Seconds 1
        }
    }
}
else {
    $metricsJob = Start-Job -ArgumentList @($ProcessNames, $metricsPath, $Label) -ScriptBlock {
        param($names, $path, $scenarioLabel)
        while ($true) {
            $timestamp = Get-Date -Format o
            foreach ($name in $names) {
                $processes = Get-Process -Name $name -ErrorAction SilentlyContinue
                foreach ($process in $processes) {
                    $cpu = if ($null -ne $process.CPU) { [math]::Round($process.CPU, 2) } else { 0 }
                    $memoryMb = [math]::Round($process.WorkingSet64 / 1MB, 2)
                    Add-Content -Path $path -Value "$scenarioLabel,$timestamp,$($process.ProcessName),$cpu,$memoryMb"
                }
            }
            Start-Sleep -Seconds 1
        }
    }
}

try {
    $locustOutput = & pipenv run locust -f $locustPath `
        --headless `
        --host $HostUrl `
        --users $Users `
        --spawn-rate $SpawnRate `
        --run-time $RunTime `
        --only-summary 2>&1 | Out-String -Width 5000

    Add-Content -Path $resultsPath -Value $locustOutput
}
finally {
    if ($metricsJob) {
        Stop-Job $metricsJob -ErrorAction SilentlyContinue | Out-Null
        Remove-Job $metricsJob -Force -ErrorAction SilentlyContinue | Out-Null
    }
}
