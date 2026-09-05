# design-lab — 채용 상세페이지 디자인 랩 (포트 8780)

기존 파이프라인과 **완전히 분리된** 기능이다. 여기서 확정되기 전까지 `jd-viewer/` 는
건드리지 않는다. 크롤 데이터도 안 읽고 안 쓴다 — 이 폴더 안에서만 논다.

```
python design-lab/serve.py          # http://localhost:8780
python design-lab/serve.py --port 9100
```

## 왜 있나

`jd-viewer` 의 공고 상세(`src/components/JobDetail.tsx`)를 새로 짜기 전에,
남들이 '상세'를 어떻게 접는지부터 본다. 예쁜 화면 구경이 아니라 **레이아웃 /
섹션 순서 / 카피 / 강약 만드는 법** 을 떼어 보는 게 목적이다.

## 구조

```
design-lab/
  serve.py            # 정적 서버 + /api/refs.json + /refs/<파일>
  refs.json           # 레퍼런스 메타 + 건별 분석(읽은 것 / 가져올 것 / 버릴 것) + 종합
  refs/instagram/posts/   # 포스트 개별 캡처
  refs/NOTES.md       # 수집 노트, 현업 레퍼런스 사이트 목록
  static/index.html   # 갤러리 화면 (빌드 없음, 바닐라)
```

파일명 규칙: `<계열>-<번호>_<계정>[_<postcode>]_s<슬라이드>.jpg`
계열은 `detail`(커머스 상세) / `hire`(채용).

## 수집 방법

인스타그램은 로그인 세션이 필요해서 Playwright 로는 못 긁는다. 사용자 Chrome
(claude-in-chrome)으로 해시태그 그리드를 열고 **포스트를 하나씩 열어** 캡처한다.
그리드 통째 캡처는 나중에 관리가 안 되므로 쓰지 않는다.

1. `https://www.instagram.com/explore/tags/<태그>/` 진입 후 이미지 로드까지 대기
2. 첫 포스트 클릭 → 모달 진입
3. 캡처 → 모달 오른쪽 바깥 화살표로 다음 포스트. 캐러셀은 이미지 위 화살표로 슬라이드 이동
4. `refs.json` 에 항목 추가 (분석 세 줄은 반드시 채운다)

돌아 본 태그: `#상세페이지디자인` `#채용포스터` `#recruitmentposter` `#채용공고`

## 아직 안 한 것

- 캡처에 인스타 UI(캡션 패널·사이드바)가 같이 찍혀 있다. 이미지 영역만 잘라내면 더 깔끔하다
- 기업 채용 사이트(토스·당근·쿠팡) 실제 상세 화면은 아직 안 모았다
- 레퍼런스를 바탕으로 한 상세페이지 시안 자체는 아직 없다
