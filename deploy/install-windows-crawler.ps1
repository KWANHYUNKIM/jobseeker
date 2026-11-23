# 채용 크롤을 윈도우 PC 에서도 돌린다 — 맥 deploy/setup-crawler.sh(launchd)의 윈도우판.
# 작업 스케줄러에 셋을 등록한다. 이름은 launchd 라벨에서 com. 을 뺀 꼴(8770 대시보드가 이 이름으로 찾는다).
#
#   jobseeker-crawler     1시간마다  python -m automation.auto_crawl once <키워드> 50   (회차: 크롤 → 통합·DB → 뷰어 …)
#   jobseeker-closecheck  10분마다   python -m pipeline.close_check --limit 100        (마감 재확인)
#   jobseeker-albacheck   30분마다   python -m crawlers.crawl_alba --check --recheck 60 (컴퓨터 알바 마감 확인)
#
# 겹침: 작업마다 MultipleInstances=IgnoreNew(앞 회차가 길어지면 다음 회차를 건너뛴다) + 코드 쪽 잠금
# (auto_crawl.run.lock · job_closures.lock · alba.lock). 맥에서도 같은 크롤이 돌면 같은 사이트를 두 번 긁는다 — 한쪽만 켠다.
#
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows-crawler.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\install-windows-crawler.ps1 -Remove
#
# 로그: catch_capture\var\crawler\{crawler,closecheck,albacheck}.log
param([switch]$Remove, [switch]$NoStart)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$catch = Join-Path $root "catch_capture"
$py = Join-Path $catch ".venv\Scripts\python.exe"
$logDir = Join-Path $catch "var\crawler"
$keyword = if ($env:CRAWL_KEYWORD) { $env:CRAWL_KEYWORD } else {
  "개발자,프론트엔드,백엔드,풀스택,안드로이드,iOS,데이터엔지니어,데이터분석,머신러닝,AI,데브옵스,클라우드,플랫폼엔지니어,SRE,보안,자바,파이썬,자바스크립트,리액트,노드,임베디드,펌웨어,C#,컴퓨터비전,신입개발자,SI개발자"
}
$jobs = @(
  @{ name = "jobseeker-crawler";    every = 60; limit = [TimeSpan]::FromHours(3);   log = "crawler.log"
     args = "-m automation.auto_crawl once `"$keyword`" 50";  desc = "채용 크롤 회차(맥 com.jobseeker.crawler 와 같은 일)" },
  @{ name = "jobseeker-closecheck"; every = 10; limit = [TimeSpan]::FromMinutes(30); log = "closecheck.log"
     args = "-m pipeline.close_check --limit 100";             desc = "마감 재확인 100건(맥 com.jobseeker.closecheck)" },
  @{ name = "jobseeker-albacheck";  every = 30; limit = [TimeSpan]::FromMinutes(30); log = "albacheck.log"
     args = "-m crawlers.crawl_alba --check --recheck 60";     desc = "컴퓨터 알바 마감 확인(맥 com.jobseeker.albacheck)" }
)

if ($Remove) {
  foreach ($j in $jobs) {
    Stop-ScheduledTask -TaskName $j.name -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $j.name -Confirm:$false -ErrorAction SilentlyContinue
  }
  Write-Output "지웠다: $(($jobs | % { $_.name }) -join ', ')"
  return
}

if (-not (Test-Path $py)) { throw "가상환경이 없다: $py" }
New-Item -ItemType Directory -Force $logDir | Out-Null

foreach ($j in $jobs) {
  # cmd /c 로 감싸 출력을 로그로 돌린다. chcp 65001 + PYTHONIOENCODING 으로 한글 키워드·로그가 깨지지 않게.
  $cmd = "/c chcp 65001 >nul & set PYTHONIOENCODING=utf-8& set PYTHONUNBUFFERED=1& `"$py`" $($j.args) >> `"$logDir\$($j.log)`" 2>&1"
  $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $cmd -WorkingDirectory $catch
  # 지금부터 every 분마다 무기한 반복(로그온 여부와 상관없이 시각 트리거로 돈다 — 로그온해 있을 때만)
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $j.every)
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit $j.limit -MultipleInstances IgnoreNew
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskName $j.name -Description $j.desc -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal -Force | Out-Null
  Write-Output "등록: $($j.name) — $($j.every)분마다"
}
if (-not $NoStart) {
  Start-ScheduledTask -TaskName "jobseeker-crawler"
  Write-Output "첫 회차 시작: jobseeker-crawler (로그 $logDir\crawler.log)"
}
