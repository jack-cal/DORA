# Allow only SUMUWW's listening TCP port. Other firewall rules remain enabled.
$ErrorActionPreference = 'Stop'
function Save-SumuwwFirewallRecord {
    param([string]$Path, [string]$RuleName)

    # This optional record is created once. Never truncate an existing file:
    # it may be a legacy wallet, a link to one, or a file created concurrently.
    try {
        $sumuwwStream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    } catch [IO.IOException] {
        $sumuwwErrorCode = $_.Exception.HResult -band 0xffff
        if ($sumuwwErrorCode -eq 80 -or $sumuwwErrorCode -eq 183) {
            return
        }
        throw
    }
    try {
        $sumuwwJson = @{ rule = $RuleName; tcp_port = 18444; enabled_at = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json
        $sumuwwBytes = [Text.UTF8Encoding]::new($false).GetBytes($sumuwwJson + [Environment]::NewLine)
        $sumuwwStream.Write($sumuwwBytes, 0, $sumuwwBytes.Length)
        $sumuwwStream.Flush($true)
    } finally {
        $sumuwwStream.Dispose()
    }
}

$sumuwwIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$sumuwwPrincipal = [Security.Principal.WindowsPrincipal]::new($sumuwwIdentity)
if (-not $sumuwwPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $sumuwwScript = $PSCommandPath
    $sumuwwArguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $sumuwwScript + '"'
    $sumuwwElevated = Start-Process -FilePath 'powershell.exe' -ArgumentList $sumuwwArguments -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    exit $sumuwwElevated.ExitCode
}
$sumuwwRuleName = 'SUMUWW-P2P-TCP-18444'
$sumuwwExisting = Get-NetFirewallRule -Name $sumuwwRuleName -ErrorAction SilentlyContinue
if ($null -eq $sumuwwExisting) {
    New-NetFirewallRule -Name $sumuwwRuleName -DisplayName 'SUMUWW node TCP 18444' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 18444 -Profile Any | Out-Null
} else {
    $sumuwwPort = $sumuwwExisting | Get-NetFirewallPortFilter
    if ([string]$sumuwwPort.LocalPort -ne '18444' -or [string]$sumuwwPort.Protocol -ne 'TCP') {
        throw 'Existing SUMUWW rule has unexpected port settings; it was not changed.'
    }
    Set-NetFirewallRule -Name $sumuwwRuleName -Enabled True -Direction Inbound -Action Allow -Profile Any
}
$sumuwwRecord = Join-Path $env:LOCALAPPDATA 'SUMUWW\public-firewall.json'
New-Item -ItemType Directory -Path (Split-Path -Parent $sumuwwRecord) -Force | Out-Null
Save-SumuwwFirewallRecord -Path $sumuwwRecord -RuleName $sumuwwRuleName
