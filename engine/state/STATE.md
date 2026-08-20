# 진행 상황

엔진은 실행 사이에 기억이 없다. 다음 사이클이 이어받을 맥락을 여기에 남긴다.

## 지금 파는 중

**네이버 — 기능 1개(`colbert-matching`).** 도메인 5개 중 랭킹·매칭만 채워졌다.
남은 도메인: 질의 이해 / 문서 색인 / 커머스 데이터 / 지면 구성.

**이 회사는 토스보다 자료가 어렵다.** deview.naver.com 과 그 PDF 는 fetch 가 막혀 있고
d2.naver.com 은 검색에 잘 안 잡힌다. 지금까지 쓸 수 있었던 건 검색 결과에 노출되는
세션 개요뿐이다. 그래서 confirmed 가 얇고 기법 자체는 논문으로 보강했다 — 그 둘을
섞지 말 것(회사가 한 말 / 기법의 일반 성질 / 우리 추론).

## 사이클 로그

| 사이클 | 날짜 | 회사 | 한 일 | 다음 |
|---|---|---|---|---|
| 000 | 2026-08-20 | — | 엔진 골격(PROMPT·schema·QUEUE·index) 생성 | 토스 프로파일 |
| 001 | 2026-08-20 | 토스 | 회사 프로파일(비즈니스 모델·수익원·도메인 4개) + 기능 `instant-transfer` 역설계 | 코어뱅킹 도메인 |
| 002 | 2026-08-20 | 토스 | 코어뱅킹 `interest-accrual`(지금 이자 받기) — MSA 분리·계좌 락·세금 비동기·이자 캐시 | 결제 도메인 |
| 003 | 2026-08-20 | 토스 | 결제 `payment-approval`(승인·취소) — 3-Step·Bridge·Converter·카나리 자동롤백·API 버저닝 | 인증 도메인 |
| 004 | 2026-08-20 | 토스 | 인증 `request-passport` — Gateway 중앙화·요청 서명·Passport 전파·FDS 연계 | 토스인증서(전자서명) |
| 005 | 2026-08-20 | 토스 | 인증 `identity-certificate`(토스인증서) + **완주 판정 → done** | 네이버 프로파일 |
| 006 | 2026-08-20 | — | STYLE.md 신설(그림·도메인 기술·생각·결정 세분화) · schema/validator/뷰어 확장 · 토스 재개 | 토스 `instant-transfer` 심화 |
| 007 | 2026-08-20 | 토스 | `instant-transfer` 심화 — 그림 3장(흐름·상태·실패) · thinking 4 · 결정 3→7 | `interest-accrual` 심화 |
| 008 | 2026-08-20 | 토스 | `interest-accrual` 심화 — 그림 3장 · thinking 4 · 결정 4→7 (경고 16→13) | `payment-approval` 심화 |
| 009 | 2026-08-20 | 토스 | `payment-approval` 심화 — status 8종 상태도 · 그림 3장 · thinking 4 · 결정 5→8 (경고 13→11) | `request-passport` 심화 |
| 010 | 2026-08-20 | 토스 | `request-passport` 심화 — 그림 3장 · thinking 4 · 결정 4→7 · Zero Trust 범위 오류 수정 (경고 11→8) | `identity-certificate` 심화 |
| 011 | 2026-08-20 | 토스 | `identity-certificate` 심화 — 그림 3장 · thinking 4 · 결정 4→6 (경고 8→5) | domain_map + 도메인 tech[] |
| 012 | 2026-08-20 | 토스 | domain_map + 도메인 4개 tech[] (경고 5→0) · **완주 재판정 → done** | 네이버 프로파일 |
| 013 | 2026-08-20 | 네이버 | 프로파일 — 수익 5부문 · 도메인 5개(질의이해·색인·랭킹·커머스데이터·지면구성) · domain_map | 첫 기능(자동완성) |
| 014 | 2026-08-20 | 네이버 | 자동완성 자료 없어 대상 교체 → `colbert-matching` 역설계(그림 3장·thinking 4·결정 6) | 질의 이해 도메인 |

## 다음 사이클 메모

- **자동완성은 포기했다.** 네이버가 직접 밝힌 자료가 없고 일반적인 trie/FST 설명만
  나온다. 남의 일반론을 이 회사의 선택인 것처럼 쓰면 이 사이트 전체가 못 믿을 것이 된다.
  QUEUE 의 '첫 기능' 메모는 그래서 틀렸다 — 자료가 있는 기능으로 골라야 한다.
- 다음은 **질의 이해** 도메인의 D.I.A.+ / 의도 분석(Intent Query·Intent Walker·User
  Preference). DEVIEW 세션 자료가 검색 결과에 요약으로 노출되므로 confirmed 를 조금은
  붙일 수 있다.
- 그 다음 후보: 커머스 데이터(쇼핑 검색 커버리지), 문서 색인(검색 모니터링).
  `지면 구성`은 기술 자료가 없어 마지막까지 비어 있을 가능성이 높다 — 억지로 채우지 않는다.
- 접근 제약 메모: deview.naver.com(및 그 PDF), blog.naver.com 은 fetch 불가.
  deview.kr 은 301 로 deview.naver.com 에 넘긴다. arxiv 등 논문은 접근 가능.
