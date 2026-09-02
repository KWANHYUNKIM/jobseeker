# 서버 운영 가이드

이 맥북(`yujeoui-MacBookAir`)을 jobseeker 서버로 운영하기 위한 문서.

## 구성

```
  다른 컴퓨터 ──SSH──▶ 맥북 서버 (192.168.45.241)
       │                  │
       └──HTTP:8080──────▶├─ jobseeker-viewer  (nginx)   ← 기본: LAN 전용
                          │
  GitHub ◀──아웃바운드───  ├─ actions-runner (launchd)
   push                   │      └ push 감지 → deploy.sh
                          │
                          └─ (선택) cloudflared ──아웃바운드──▶ Cloudflare ──HTTPS──▶ 인터넷
```

기본 구성은 **LAN 전용**이다. 도메인 없이 혼자 보는 용도라 같은 네트워크에서
`http://192.168.45.241:8080` 으로 바로 접속한다. 공유기 포트포워딩도 DDNS도
인증서도 필요 없다.

밖에서 봐야 할 때만 터널을 켠다. 어느 쪽이든 **인바운드 포트는 열지 않는다** —
터널도 러너도 밖으로 나가는 커넥션만 맺는다.

| 접근 방식 | 프로필 | 주소 | 비고 |
|---|---|---|---|
| LAN 전용 (기본) | — | `http://192.168.45.241:8080` | 도메인·계정 불필요 |
| 임시 공개 | `quick` | `https://*.trycloudflare.com` | 계정 불필요, **재시작마다 주소 변경** |
| 고정 공개 (무료) | `ngrok` | `https://<내>.ngrok-free.dev` | ngrok 계정 필요, 도메인 불필요 |
| 고정 공개 (도메인) | `tunnel` | 내 도메인 | 도메인 + Cloudflare 토큰 필요 |

```bash
COMPOSE_PROFILES=quick docker compose -f docker-compose.prod.yml up -d
./deploy/tunnel-url.sh          # 지금 떠 있는 주소 확인
```

**밖에서 상시로 쓸 거면 `quick` 은 부적합하다.** 주소가 재시작마다 바뀌는데,
새 주소를 알려면 서버에 붙어야 한다. 회사에서 쓸 거라면 `ngrok` 정적 도메인
(무료 플랜에 1개 포함)으로 고정해두는 편이 낫다.

## 파일

| 파일 | 역할 |
|---|---|
| `../docker-compose.prod.yml` | 뷰어 + (선택) 터널. 터널은 compose 프로필로 분리 |
| `../.env` | 선택. `VIEWER_BIND`, `CLOUDFLARE_TUNNEL_TOKEN` (커밋 금지) |
| `deploy.sh` | 배포 — 동기화 → 빌드 → 기동 → 헬스체크 |
| `setup-server.sh` | OS 설정 — SSH 켜기, 절전 해제 (sudo 필요) |
| `setup-runner.sh` | GitHub Actions 러너 설치 |
| `setup-crawler.sh` | 크롤 파이프라인 설치(venv·Playwright) + launchd 주기 실행 |
| | `--reschedule` 은 plist 만 갱신한다. `deploy.sh` 가 매 배포마다 불러 인자 드리프트를 막는다 |
| `tunnel-url.sh` | 지금 떠 있는 공개 주소 확인 |
| `sshd_jobseeker.conf` | SSH 강화 설정 (비밀번호 로그인 차단) |
| `../.github/workflows/ci.yml` | 린트·타입체크·빌드 (GitHub 클라우드 러너) |
| `../.github/workflows/deploy.yml` | main push → 이 서버에서 재배포 |

## 일상 운영

```bash
cd ~/jobseeker

# 상태 확인
docker compose -f docker-compose.prod.yml ps

# 로그
docker compose -f docker-compose.prod.yml logs -f viewer

# 밖에서 봐야 할 때 (임시 공개 주소 발급 — 주소는 로그에 찍힌다)
COMPOSE_PROFILES=quick docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs quicktunnel | grep trycloudflare

# 수동 재배포 (origin/main 동기화 포함)
./deploy/deploy.sh

# 현재 워킹트리 그대로 재배포 (동기화 생략)
./deploy/deploy.sh --local

# 정지
docker compose -f docker-compose.prod.yml down
```

## 크롤러

뷰어와 달리 **컨테이너가 아니라 호스트에서 네이티브로 돈다.** Playwright가 실제
브라우저를 띄우고 사이트마다 봇 탐지를 상대해야 해서 컨테이너 안 헤드리스보다
안정적이고, `paths.py`·`refresh-data.sh`도 `catch_capture/.venv`를 전제로 한다.

```bash
./deploy/setup-crawler.sh               # venv + Playwright 설치만
./deploy/setup-crawler.sh --schedule    # 위 + launchd 1시간 주기 등록
./deploy/setup-crawler.sh --reschedule  # plist 만 최신 기본값으로 갱신 (deploy.sh 가 자동 호출)
./deploy/setup-crawler.sh --uninstall   # 스케줄 해제 (venv·데이터는 유지)

# 수동 1회 실행
cd catch_capture && .venv/bin/python -m automation.auto_crawl once 개발자 100

# 상태·로그
launchctl print gui/$(id -u)/com.jobseeker.crawler | head -20
tail -f ~/Library/Logs/jobseeker-crawler.out.log
launchctl kickstart -k gui/$(id -u)/com.jobseeker.crawler   # 즉시 1회
```

`auto_crawl start`(자체 데몬) 대신 `once`를 launchd `StartInterval`로 돌린다.
PID 파일 관리가 사라지고, 한 사이클이 주기보다 길어져도 launchd가 같은 job을
중복 실행하지 않는다.

### 스냅샷 이력이 먼저다

`build_trends.py`는 기존 `trends.json`을 **병합하지 않고**
`catch_capture/screenshots/all_통합_*` 스냅샷에서 통째로 다시 만든다. 이력이
없는 상태로 크롤을 돌리면 17일치 시계열이 하루치로 무너진다.
`setup-crawler.sh --schedule`은 이력이 없으면 등록을 거부한다.

옛 서버에서 가져오려면:
```bash
rsync -av <계정>@<옛서버>:jobseeker/catch_capture/screenshots/ \
          ~/jobseeker/catch_capture/screenshots/
```

### 생성 데이터는 git 으로 나르지 않는다

`jd-viewer/public/*.json`, `catch_capture/dashboard/data.json` 은 `.gitignore` 대상이다.
크롤 파이프라인이 매 사이클 다시 만드는 파생물이고, git 에 넣으면 두 가지가 깨진다.

1. 사이클마다 수십 MB 가 바뀌어 이력이 데이터 커밋으로 뒤덮인다.
2. 크롤러가 워킹트리를 상시 더럽혀 `deploy.sh` 의 `git merge --ff-only` 가 막힌다.
   실제로 2026-08-17~18 배포가 이 이유로 연달아 실패했고, 뷰어가 낡은 이미지로
   이틀간 서비스되면서 검색 API 프록시가 빠진 채 돌았다.

그래서 크롤러의 자동 커밋(`JOBSEEKER_AUTOPUSH`)도 없앴다. 데이터는 read-only
볼륨(`./jd-viewer/public:/data:ro`)으로 마운트되므로 파일만 바뀌면 뷰어에 즉시 반영된다.

**데이터를 옮겨야 할 때**
- 다른 서버로 이사: `./deploy/seed-server.sh <계정>@<호스트>` — 누적 폴더와 뷰어
  데이터를 rsync 로 함께 나른다.
- 데이터가 축소·손상됐을 때: 누적 폴더(`screenshots/{사이트}_{키워드}`)가 원본이므로
  `jd-viewer/bin/refresh-data.sh` 로 다시 만든다. 이 스크립트에는 급감 가드가 있어
  건수가 절반 미만으로 떨어지면 덮어쓰지 않고 멈춘다.

## 관리 대시보드

크롤 상태·통계를 보는 서버 2종. 호스트 네이티브(launchd)로 돌고, 각각 별도
임시 터널로 외부에 노출한다.

| 포트 | 서버 | 역할 |
|---|---|---|
| 8770 | ops (`monitoring.ops_server`) | 크롤 파이프라인 **실시간** 운영 대시보드 |
| 8765 | stats (`dashboard/serve.py`) | 공고 분류·집계 통계 대시보드 |

```bash
./deploy/setup-dashboards.sh              # 두 서버를 launchd 로 등록·기동
# .env 의 COMPOSE_PROFILES 에 dashboards 를 넣고 배포하면 터널이 함께 뜬다
./deploy/tunnel-url.sh                     # ops/stats 공개 주소 확인
./deploy/setup-dashboards.sh --uninstall   # 해제
```

⚠️ **두 대시보드 모두 인증이 없다.** 터널 주소를 아는 사람은 누구나 본다.
데이터가 채워지려면 크롤러가 돌아야 한다(그전엔 빈 화면·0건).

🔒 **admin(8910, `admin/server.py`)은 절대 터널에 붙이지 않는다.** 개인 이력·
지원 내역·API 키를 다루고, 저장소에서도 `catch_capture/admin/`이 커밋 금지다.
필요하면 LAN(`http://192.168.45.241:8910`)이나 SSH 포트포워딩으로만 접근한다.

## 다른 컴퓨터에서 작업하기

서버에 직접 붙어서 코딩할 필요는 없다. 개발은 각자 컴퓨터에서 하고,
`main`에 push하면 서버가 알아서 당겨받아 재배포한다.

### 1) 개발 루프 (SSH 없이)

```bash
git clone https://github.com/KWANHYUNKIM/jobseeker.git
cd jobseeker/jd-viewer && npm ci && npm run dev   # localhost:5173

# 작업 후
git switch -c feat/something
git commit -am "feat(viewer): ..." && git push -u origin feat/something
# → PR을 열면 CI(빌드·타입체크)가 돌고, main에 머지되면 서버가 자동 배포
```

배포 결과는 GitHub의 Actions 탭에서 확인한다. 서버에 접속할 일이 없다.

### 2) 서버 SSH 접속 (로그 확인·긴급 대응용)

서버에서 만든 개인키 `~/.ssh/server_access_ed25519`를 클라이언트로 옮긴다.
**공개키가 아니라 개인키**이므로 안전한 경로로 옮기고 서버 쪽에는 그대로 둔다.

```bash
# 클라이언트에서
chmod 600 ~/.ssh/jobseeker_server
cat >> ~/.ssh/config <<'EOF'
Host jobseeker
  HostName 192.168.45.241     # 같은 네트워크일 때. 외부면 아래 참고
  User user
  IdentityFile ~/.ssh/jobseeker_server
  IdentitiesOnly yes
EOF

ssh jobseeker
```

외부망에서 붙어야 하면 SSH 포트를 여는 대신 **Cloudflare Access for SSH**를
쓴다. 터널을 이미 쓰고 있으므로 추가 포트 개방이 필요 없고, 공인 IP가 바뀌어도
영향이 없다.

### 3) 수동 배포 트리거

코드 변경 없이 다시 배포하고 싶으면 GitHub Actions 탭에서 **Deploy → Run
workflow**를 누른다(`workflow_dispatch`). 서버 앞에 앉을 필요가 없다.

## 알아둘 것

- **맥북 절전.** `setup-server.sh`가 `pmset -a disablesleep 1`을 걸어 뚜껑을 닫아도
  안 잠들게 한다. 이걸 안 하면 뚜껑 닫는 순간 터널과 러너가 같이 죽는다.
- **뷰어는 LAN에 열려 있다.** `0.0.0.0:8080` 바인딩이라 같은 네트워크의 아무나
  볼 수 있다. 집 네트워크면 문제없지만 카페 같은 공용 와이파이에 물릴 일이 있으면
  `.env`에 `VIEWER_BIND=127.0.0.1`을 넣어 로컬로 좁힌다.
- **임시 터널 주소는 공개 URL이다.** `quick` 프로필로 뜨는 `*.trycloudflare.com`
  주소는 추측하기 어렵지만 인증이 없다. 주소를 아는 사람은 누구나 볼 수 있다.
- **Docker Desktop은 사용자 앱이다.** 재부팅 후 *사용자가 로그인해야* 데몬이 뜬다.
  완전 무인 재부팅이 필요하면 자동 로그인을 켜거나 colima를 LaunchDaemon으로
  돌리는 쪽으로 바꿔야 한다. (colima도 이미 설치되어 있음)
- **데이터 볼륨.** `jd-viewer/public`을 read-only로 마운트하므로 크롤러가 JSON을
  갱신하면 **재빌드 없이 즉시** 반영된다.
- **`jd-viewer/public/all_jobs.json`은 추적하지 않는다.** gitignore 대상인
  `catch_capture/screenshots/`를 가리키는 심링크였고, 클론한 트리에는 타겟이 없어
  `vite build`가 ENOENT로 죽었다. 크롤러가 로컬에 다시 만들어도 gitignore가 막는다.
- **린트는 아직 차단 게이트가 아니다.** 기존 코드에 에러 13건(`no-explicit-any` 7,
  `react-hooks/set-state-in-effect` 6)이 남아 있어 `ci.yml`에서 `continue-on-error`로
  둔다. 정리가 끝나면 그 옵션을 지우고 `deploy.yml`의 `check-name`에 추가할 것.
- **페이로드가 크다.** `all_jobs_enriched.json`이 44MB(gzip 12MB)다. nginx gzip은
  켜져 있지만 터널을 통과하는 첫 로딩은 느릴 수 있다.
- **배포 동기화는 `--ff-only`다.** 로컬에 커밋 안 된 변경이나 갈라진 브랜치가 있으면
  덮어쓰지 않고 배포를 실패시킨다. 크롤러가 만든 데이터를 날리는 것보다 낫다.
