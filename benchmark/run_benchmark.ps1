param(
    [Parameter(Mandatory = $true)]
    [string]$HostUrl,

    [Parameter(Mandatory = $true)]
    [string]$Label,

    [int]$Users = 100,
    [int]$SpawnRate = 10,
    [string]$RunTime = '5m',
    [string]$ResultsFile = 'benchmark_results.txt'
)

$resultsPath = Join-Path $PSScriptRoot $ResultsFile
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

$locustOutput = & locust -f (Join-Path $PSScriptRoot 'locustfile.py') `
    --headless `
    --host $HostUrl `
    --users $Users `
    --spawn-rate $SpawnRate `
    --run-time $RunTime `
    --only-summary 2>&1 | Out-String -Width 5000

Add-Content -Path $resultsPath -Value $locustOutput