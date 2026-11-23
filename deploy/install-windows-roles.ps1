# 직무 역설계(공고 풀이) 러너를 윈도우 작업 스케줄러에 올린다 — Claude Code 세션 밖에서 돌아
# 세션이 닫히거나 메모리 정리로 백그라운드 작업이 끊겨도 계속 간다(2026-11-23).
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows-roles.ps1 [-Workers 6]
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows-roles.ps1 -Remove
#   일꾼을 더 붙일 때(도는 것을 끊지 않고): -Workers 3 -First 7 -Suffix 2  → 작업 jobseeker-roles-2, 일꾼 7~9
param([int]$Workers = 6, [int]$First = 1, [string]$Suffix = "", [switch]$Remove)

$Name = if ($Suffix) { "jobseeker-roles-$Suffix" } else { "jobseeker-roles" }
$Root = Split-Path -Parent $PSScriptRoot
$Cc = Join-Path $Root "catch_capture"
$Py = Join-Path $Cc ".venv\Scripts\python.exe"
$LogDir = Join-Path $Cc "var\loops\role-engine"

if ($Remove) {
    Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    "removed $Name"
    return
}

New-Item -ItemType Directory -Force $LogDir | Out-Null
$cmd = "/c set PYTHONIOENCODING=utf-8& cd /d `"$Cc`" && `"$Py`" -m automation.loops repeat role-engine --every 1m --workers $Workers --first $First >> `"$LogDir\runner$Suffix.log`" 2>&1"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd -WorkingDirectory $Cc
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $Name
"registered $Name (workers $First..$($First+$Workers-1)) — log $LogDir\runner$Suffix.log"
