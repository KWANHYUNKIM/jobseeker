# 올리브영 매장은 가게일까, 창고일까 — 3D 해부도 릴스 생성 가이드

archcutaway(건축해부도)처럼 **3D 절단면 영상이 주인공**이고, 한글 자막·출처·음악은 우리가 얹는다(`python -m poster.cutaway reels/oliveyoung_3d`).
생성 도구에는 **글자를 넣지 말라고** 한다 — 한글이 깨진다. 로고·간판·실제 매장 재현도 넣지 않는다(회사 사칭처럼 보인다).

## 절차

1. **정지 그림** — Nano Banana(Gemini 이미지) 또는 Midjourney에 장면마다 `이미지 프롬프트` 를 넣는다. 비율 9:16.
   같은 매장이 여러 장면에 나오므로 shot02 그림을 뽑은 뒤 shot05 부터는 그 그림을 **참고 이미지로 함께 넣어** 모양을 맞춘다.
2. **움직임** — 그 그림을 Kling(Image to Video) 또는 Veo(Flow)에 넣고 `움직임 프롬프트` 를 쓴다. 5초, 9:16.
3. 받은 파일을 `reels/oliveyoung_3d/clips/` 에 **장면 이름 그대로** 저장한다 — `shot01.mp4` … `shot09.mp4`.
   영상이 없으면 그림만(`shot03.png`) 넣어도 된다 — 천천히 당겨 들어가는 움직임으로 대신한다.
4. 알려 주면 조립·검수·게시는 이쪽에서 한다.

## 모든 장면에 붙이는 스타일 문장(프롬프트 끝에 그대로)

```
clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

## shot01 · 3.5초

**자막** 올리브영 매장은 가게일까, 창고일까?

**이미지 프롬프트**
```
Aerial isometric cutaway of a Korean city block at dusk, one small health and beauty store on a street corner glowing with soft olive green light, surrounding buildings muted gray. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
slow cinematic push-in from high aerial toward the glowing store, slight orbit to the right, 4 seconds. Keep everything else still, no text appears, no logos.
```

## shot02 · 4.5초

**자막** 전국 약 1,300곳 — 파는 곳이면서 온라인 주문의 물류 거점

**이미지 프롬프트**
```
Isometric cutaway of the same small health and beauty store with the roof and front wall sliced away: front half is a bright shop floor with low shelves of cosmetic bottles, back half is a compact stock room with stacked boxes and a packing table. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
the roof lifts off and the front wall slides away to reveal the interior section, camera tilts down, 5 seconds. Keep everything else still, no text appears, no logos.
```

근거: 매장 약 1,300개 · 오늘드림 구조 — 트렌드라이트, 바이라인네트워크, 원티드 공고 337437 (guide cjoliveyoung business)

## shot03 · 4.0초

**자막** 오후 2시, 앱에서 주문 하나 — 어느 매장에서 보낼까?

**이미지 프롬프트**
```
Close-up of a hand holding a smartphone with a blank glowing screen, a thin beam of olive green light rising from the phone toward a miniature isometric city map floating above it with dozens of small glowing store pins. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
camera rises from the phone following the light beam up to the floating city map, pins light up one by one, 4 seconds. Keep everything else still, no text appears, no logos.
```

## shot04 · 5.0초

**자막** 가까운 매장에서 3시간 안에 — 오늘드림

**이미지 프롬프트**
```
Top-down isometric 3D city map with many small store pins, one pin highlighted in coral, a glowing path line running from that store along the streets to a small apartment building, a tiny delivery motorbike on the path. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
the coral path draws itself from the store to the apartment while the motorbike moves along it, gentle camera orbit, 5 seconds. Keep everything else still, no text appears, no logos.
```

근거: 오늘드림 3시간 배송 — guide cjoliveyoung business

## shot05 · 4.5초

**자막** 같은 재고를 손님과 온라인 주문이 동시에 잡는다

**이미지 프롬프트**
```
Cutaway close-up of one store shelf with a single product box glowing, on the left a stylized shopper figure reaching for it, on the right a stylized store staff picker with a basket reaching for the same box, faceless simple 3D figures. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
both hands move toward the same box at the same moment, the box pulses coral, freeze just before contact, 4 seconds. Keep everything else still, no text appears, no logos.
```

근거: 재고가 판매와 배송에 동시에 쓰임 — guide cjoliveyoung revenue(온라인몰·오늘드림)

## shot06 · 5.0초

**자막** 45분 걸리던 반영을 거의 실시간으로 — 배치와 스트리밍을 함께

**이미지 프롬프트**
```
Isometric cutaway of a data center floor visualized as two parallel conveyor belts: the left belt slow carrying large crates in batches beside a large analog clock, the right belt fast carrying a continuous stream of small glowing olive green packets, both belts running side by side. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
camera tracks sideways along the two belts, the right stream flows fast while the left moves in slow batches, 5 seconds. Keep everything else still, no text appears, no logos.
```

근거: 올리브영 테크블로그 2026-04-22 display-benefits-migration (45분 배치 → Kafka 준실시간, 하이브리드)

## shot07 · 4.0초

**자막** 새 구조를 기존 결과와 나란히 놓고 검증했다

**이미지 프롬프트**
```
Two transparent glass data tables floating side by side in a clean white space, rows of small glowing cells, matching cells connected by thin olive green lines. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
matching rows light up in sequence from top to bottom with green check pulses, slow dolly-in, 4 seconds. Keep everything else still, no text appears, no logos.
```

근거: Shadow Table 검증 — 올리브영 테크블로그 2026-04-22

## shot08 · 4.0초

**자막** 성과는 숫자로 — DB 부하 97.2% 감소

**이미지 프롬프트**
```
A tall 3D bar made of stacked database disks next to a very short bar, clean studio lighting, olive green accent on the short bar. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
the tall stack collapses down to the short height, disks sliding away, camera slight orbit, 4 seconds. Keep everything else still, no text appears, no logos.
```

근거: buffer_gets 97.2% 감소 — 올리브영 테크블로그 2026-04-22

## shot09 · 5.0초

**자막** 지원자라면: 주문 상태 전이 · 재고 동시성 · 숫자로 말하기

**이미지 프롬프트**
```
A young job applicant figure seen from behind sitting at a desk with a laptop, three translucent floating 3D cards above the desk (one with a flow of arrows, one with two hands on a box, one with a bar chart icon), warm evening desk lamp. clean stylized 3D isometric cutaway render, architectural section view, soft global illumination, matte clay-like materials, warm white and light gray base with olive green (#82DC28) and coral (#FF7878) accents, shallow depth of field, cinematic, high detail, vertical 9:16 composition, NO text, NO letters, NO logos, NO brand signage, NO watermark
```

**움직임 프롬프트**
```
the three cards float up one after another and rotate slightly toward the camera, slow push-in, 5 seconds. Keep everything else still, no text appears, no logos.
```

근거: guide cjoliveyoung domains[0].what_to_know · people[0].what_it_means

## 마지막 장면

우리가 그린다 — "저장해 두고 / 테크블로그부터", 자리 목록은 [회사 해부] 올리브영 게시물에서.
