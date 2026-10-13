# One-shot fix: release host port 8000 stolen by WinNAT excluded ranges, then start emergency-plan-backend.
# Flow: stop winnat (release ranges) -> start container (grab 8000) -> start winnat (re-allocate avoiding 8000).
# Must run elevated (launched by Codex via Start-Process -Verb RunAs).
# Kept ASCII-only + no-space path so elevation argument passing cannot garble it.

$log = 'C:\Users\55061\AppData\Local\Temp\fix-port8000.log'
$docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'

function Log([string]$m) { $m | Out-File -FilePath $log -Append -Encoding UTF8 }
function Run([scriptblock]$sb) {
    $out = & $sb 2>&1 | Out-String
    $out | Out-File -FilePath $log -Append -Encoding UTF8
    $out
}

"=== fix-port8000 start $(Get-Date -Format o) ===" | Out-File -FilePath $log -Encoding UTF8
Log "IsAdmin=$(([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))"

Log '--- 1. stop winnat ---'
Run { net stop winnat }
Start-Sleep -Seconds 2
Log '--- excluded ranges after stop ---'
Run { netsh int ipv4 show excludedportrange protocol=tcp }

try {
    Log '--- 2. start backend container ---'
    Run { & $docker start emergency-plan-backend }
    Start-Sleep -Seconds 8

    Log '--- 3. verify container + port 8000 ---'
    Run { & $docker ps --filter name=emergency-plan-backend --format '{{.Names}} | {{.Status}} | {{.Ports}}' }
    Run { netstat -ano | Select-String ':8000\s' | Out-String }
}
finally {
    Log '--- 4. start winnat (always) ---'
    Run { net start winnat }
    Start-Sleep -Seconds 3
}

Log '--- 5. final re-check (container + excluded ranges) ---'
Run { & $docker ps --filter name=emergency-plan-backend --format '{{.Names}} | {{.Status}} | {{.Ports}}' }
Run { netsh int ipv4 show excludedportrange protocol=tcp }
Run { netstat -ano | Select-String ':8000\s' | Out-String }
Run { Get-Service winnat | Select-Object Name, Status | Out-String }

"=== fix-port8000 done $(Get-Date -Format o) ===" | Out-File -FilePath $log -Append -Encoding UTF8
