# 서버 운영 가이드

이 맥북(`yujeoui-MacBookAir`)을 jobseeker 서버로 운영하기 위한 문서.

## 구성

```
  다른 컴퓨터 ──SSH──▶ 맥북 서버 (192.168.45.241)
                          │
  GitHub ◀──아웃바운드───  ├─ actions-runner (launchd)
   push                   │      └ push 감지 → deploy.sh
                          │
                          ├─ jobseeker-viewer   (nginx, 127.0.0.1:8080)
                          └─ jobseeker-tunnel   (cloudflared)
                                    │
                                아웃바운드
                                    ▼
                          Cloudflare ──HTTPS──▶ 인터넷
```

핵심은 **인바운드 포트를 하나도 열지 않는다**는 것이다. 터널도 러너도 밖으로
나가는 커넥션만 맺으므로 공유기 포트포워딩·DDNS·인증서 갱신이 전부 불필요하다.
HTTPS 인증서는 Cloudflare가 자동 발급·갱신한다.

## 파일

| 파일 | 역할 |
|---|---|
| `../docker-compose.prod.yml` | 뷰어 + 터널 컨테이너 정의 |
| `../.env` | `CLOUDFLARE_TUNNEL_TOKEN` (커밋 금지) |
| `deploy.sh` | 배포 — 동기화 → 빌드 → 기동 → 헬스체크 |
| `setup-server.sh` | OS 설정 — SSH 켜기, 절전 해제 (sudo 필요) |
| `setup-runner.sh` | GitHub Actions 러너 설치 |
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
docker compose -f docker-compose.prod.yml logs -f cloudflared

# 수동 재배포 (origin/main 동기화 포함)
./deploy/deploy.sh

# 현재 워킹트리 그대로 재배포 (동기화 생략)
./deploy/deploy.sh --local

# 정지
docker compose -f docker-compose.prod.yml down
```

## 다른 컴퓨터에서 SSH 접속

개인키를 클라이언트로 옮긴 뒤:

```bash
# 클라이언트에서
chmod 600 ~/.ssh/jobseeker_server
cat >> ~/.ssh/config <<'EOF'
Host jobseeker
  HostName 192.168.45.241     # 같은 네트워크. 외부면 Cloudflare Access 사용
  User user
  IdentityFile ~/.ssh/jobseeker_server
  IdentitiesOnly yes
EOF

ssh jobseeker
```

외부망에서 접속하려면 SSH 포트를 여는 대신 **Cloudflare Access for SSH**를
쓰는 편이 낫다(터널을 이미 쓰고 있으므로 추가 포트 개방 불필요).

## 알아둘 것

- **맥북 절전.** `setup-server.sh`가 `pmset -a disablesleep 1`을 걸어 뚜껑을 닫아도
  안 잠들게 한다. 이걸 안 하면 뚜껑 닫는 순간 터널과 러너가 같이 죽는다.
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
