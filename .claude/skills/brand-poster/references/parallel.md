# 판 만들기 — 다음 회사 고르기 · 병렬로 돌리기

여러 회사를 한 번에 할 때. 원래 `design-lab/brand-poster 스킬` 였던 것을 절 번호 그대로 옮겼다.

## 1-1. 다음에 만들 회사는 묶음이 알려 준다

묶음(카테고리) 게시물은 **전용 판이 있는 회사만** 넣는다(`poster/collection.py`). 그래서 다음에
어느 회사 판을 만들어야 하는지는 묶음이 알려 준다 — 채우려는 카테고리로 물어보면 된다.

```bash
cd design-lab
python -m poster.collection gaps newgrad          # 신입 묶음에서 전용 판이 없어 빠지는 회사
python -m poster.collection gaps role --value backend
```

회사 규모 → 모집중 공고 수 순으로 나온다. 위에서부터 이 절차(아래 2절의 작업자 지시문)로 만들면
그 카테고리가 채워진다.

## 2. 병렬로 돌리기

여러 회사를 한 번에 할 때는 회사마다 작업자 하나. **파일 소유권을 나눈다.**

| 작업자가 고쳐도 되는 것 | 건드리면 안 되는 것(메인만) |
|---|---|
| `brands/<그 회사>.json` | `references/records.md` `brand-poster 스킬` `references/nanobanana.md` `README.md` |
| `poster/templates/brand_<그 회사>.html` | `poster/carousel.py` `poster/templates/_frame.js` |
| `assets/companies/<그 회사>/` | 다른 회사 파일 |
| `out/<그 공고키>/` | git 커밋 |

- 공유 브라우저(claude-in-chrome)는 작업자끼리 탭이 엉킨다 → 작업자는 WebSearch/WebFetch/curl + Playwright 헤드리스(`poster.render._page_maker`)로 캡처.
- 렌더러 변경이 필요하면 작업자는 고치지 말고 보고만 → 메인이 반영.
- 메인이 할 일: 결과 판을 **직접 열어 확인**, 비교 시트(`out/brand_compare_*.jpg`), 기록 합치기.

작업자 지시문 틀(회사·공고키·후보만 바꾼다):

```
You are a fork. Make v<N> of the <회사> brand poster (job <공고키>). Read design-lab/brand-poster 스킬 and follow it in order.
Existing files to read first: brands/<회사>.json, poster/templates/brand_<slug>.html, out/<공고키>/RECORD*.md. Keep the current render as brand_v<N-1>_ig_portrait.jpg.
1. Find the ONE signature artifact (section 2). Candidates to check: <후보 목록>. Record evidence URLs, alternatives with reasons.
2. Fonts (section 4): actual fonts + licenses; specimen image if proprietary.
3. Colors (section 5): official/pixel-sampled palette with sources; swatch image.
4. Images (section 6): put real signature imagery into the poster via "images".
5. Template + render: cd design-lab && python -m poster.carousel <공고키> --one --frame brand; look at the jpg and iterate until section 8 checklist passes and it clearly differs from v<N-1>.
6. v<N-1>_v<N>.jpg, nanobanana pack, RECORD_v<N>.md.
HARD RULES: only touch the files listed as yours in section "병렬로 돌리기". No mcp__claude-in-chrome tools. No git commits. Label unverified claims.
Final report (short): signature + evidence, alternatives, fonts/colors/images, body px, paths, remaining issues, rights.
```
