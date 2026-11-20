# 취업후기 상시 실행 — 윈도우 작업 스케줄러에 둘을 등록한다(로그온할 때 뜨고, 죽으면 다시 뜬다).
#
#   jobseeker-careers      python -m careers.cycle --forever  (수집 → 로컬 모델 추출 → 보고서 → DB 적재, 회차 사이 60초)
#   jobseeker-viewer-api   backend: python -m app.main         (8771 — 뷰어 /careers 가 읽는다)
#
# 왜 이 PC 인가: 추출은 5070 Ti 의 로컬 모델(qwen3:14b, Ollama)로 하고 DB(jobseeker-db)도 여기 있다.
# 운영 맥(8GB M1)은 Playwright 크롤과 14B 모델을 같이 올리지 못한다(CLAUDE.md 운영 주의).
#
#   powershell -ExecutionPolicy Bypass -File catch_capture\careers\install-windows-tasks.ps1 [-CareersKey <열쇠>]
#   powershell -ExecutionPolicy Bypass -File catch_capture\careers\install-windows-tasks.ps1 -Remove
#
# 로그: catch_capture\var\careers\forever.log · catch_capture\var\careers\api.log
param([string]$CareersKey = "", [switch]$Remove)

$ErrorActionPreference = "Stop"
$catch = Split-Path -Parent $PSScriptRoot
$root = Split-Path -Parent $catch
$py = Join-Path $catch ".venv\Scripts\python.exe"
$logDir = Join-Path $catch "var\careers"
$names = @("jobseeker-careers", "jobseeker-viewer-api")

if ($Remove) {
    foreach ($n in $names) {
        Stop-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
    }
    Write-Output "지웠다: $($names -join ', ')"
    return
}

if (-not (Test-Path $py)) { throw "가상환경이 없다: $py" }
New-Item -ItemType Directory -Force $logDir | Out-Null

function Register-Job([string]$name, [string]$dir, [string]$cmd, [string]$desc) {
    # cmd /c 로 감싸야 출력을 로그 파일로 돌릴 수 있다. 창은 숨긴다(-WindowStyle 은 작업 설정이 아니라 conhost 를 안 띄우는 것으로).
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c chcp 65001 >nul & set PYTHONIOENCODING=utf-8& $cmd" -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $name -Description $desc -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    Write-Output "등록·시작: $name"
}

Register-Job "jobseeker-careers" $catch `
    "`"$py`" -m careers.cycle --forever --queries 80 --sleep 60 >> `"$logDir\forever.log`" 2>&1" `
    "취업후기 수집·추출·DB 적재를 계속 돈다(automation/loops.py 의 careers)"

$keyEnv = if ($CareersKey) { "set CAREERS_KEY=$CareersKey& " } else { "" }
Register-Job "jobseeker-viewer-api" (Join-Path $root "backend") `
    "$keyEnv`"$py`" -m app.main >> `"$logDir\api.log`" 2>&1" `
    "뷰어 API 8771(정본 DB 읽기) — 뷰어 /careers 가 읽는다"
