#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu',
    [ValidateRange(1024, 65535)]
    [int]$Port = 5173,
    [string]$ResultPath
)

$ErrorActionPreference = 'Stop'
$ruleName = "WeKnora-WSL-Frontend-$Port-LAN"

try {
    # Re-run this script if the WSL address changes after a restart.
    # WSL may emit an unrelated localhost-proxy warning on stderr.
    $ErrorActionPreference = 'Continue'
    $addressOutput = & wsl.exe -d $Distribution --exec ip -4 -o addr show dev eth0 2>$null
    $wslExitCode = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($wslExitCode -ne 0) {
        throw "Cannot read the IPv4 address of WSL distribution '$Distribution'."
    }
    $addressMatch = [regex]::Match(($addressOutput -join ' '), '\binet\s+(\d+\.\d+\.\d+\.\d+)/')
    if (-not $addressMatch.Success) {
        throw 'No IPv4 address was found on the WSL eth0 interface.'
    }
    $wslAddress = $addressMatch.Groups[1].Value

    if ((Get-Service -Name iphlpsvc).Status -ne 'Running') {
        Start-Service -Name iphlpsvc
    }

    & netsh.exe interface portproxy add v4tov4 `
        listenaddress=0.0.0.0 listenport=$Port `
        connectaddress=$wslAddress connectport=$Port protocol=tcp | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to configure Windows-to-WSL port forwarding.'
    }

    # Both Wi-Fi adapters currently use the Public profile. Limit access to
    # directly connected subnets instead of allowing arbitrary remote hosts.
    $existingRule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
    if ($existingRule) {
        Set-NetFirewallRule -Name $ruleName -Enabled True -Direction Inbound `
            -Action Allow -Profile Any -Protocol TCP -LocalPort $Port `
            -RemoteAddress LocalSubnet | Out-Null
    } else {
        New-NetFirewallRule -Name $ruleName -DisplayName "WeKnora WSL frontend $Port (LAN only)" `
            -Enabled True -Direction Inbound -Action Allow -Profile Any `
            -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet | Out-Null
    }

    $addresses = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } |
        ForEach-Object { $_.IPv4Address.IPAddress })
    $result = [ordered]@{
        success = $true
        distribution = $Distribution
        wslAddress = $wslAddress
        port = $Port
        firewallRule = $ruleName
        urls = @($addresses | ForEach-Object { "http://${_}:$Port" })
    }
    if ($ResultPath) {
        $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
    }
    Write-Output "Forwarding TCP $Port to ${wslAddress}:$Port; local subnet access enabled."
    $result.urls | ForEach-Object { Write-Output $_ }
} catch {
    if ($ResultPath) {
        @{ success = $false; error = $_.Exception.Message } |
            ConvertTo-Json | Set-Content -LiteralPath $ResultPath -Encoding UTF8
    }
    Write-Error $_
    exit 1
}
