import {
  estimateBuildMin,
  estimateImageSec,
  estimateLlm,
  priceOf,
  won,
  type HwData,
  type LlmModel,
  type Part,
  type VideoScore,
} from '../lib/hardware'
import { onLinkClick } from '../lib/router'
import { paths } from '../lib/urls'

// 조립 화면의 'AI 는 얼마나 돌아가나' · '개발 작업은' 아래에 붙는 구매 안내.
//
// 표(토큰/초·빌드 분)는 '얼마나 빠른가'다. 여기는 '그래서 무슨 일을 할 수 있나'와
// '어떤 일을 하려는 사람이 어느 급을 사나'다. 숫자는 전부 같은 추정식(bench.json)과
// 오늘 가격에서 나온다 — 새 숫자를 지어내지 않는다. 급을 가르는 문턱(VRAM 8·12·16·24GB,
// 멀티 지수 40·70)은 우리가 정한 구분이고 화면에 그렇게 적는다.

type Verdict = 'good' | 'ok' | 'bad'
const MARK: Record<Verdict, string> = { good: '✓', ok: '△', bad: '✕' }
const TONE: Record<Verdict, string> = {
  good: 'text-(--color-accent)',
  ok: 'text-(--color-amber-400)',
  bad: 'text-(--color-red-400)',
}

const fmtTps = (t: number) => (t >= 10 ? Math.round(t) : t.toFixed(1))
const fmtMin = (m: number) => (m < 10 ? m.toFixed(1) : String(Math.round(m)))
const short = (p: Part) => p.name.replace('GeForce ', '').replace('Radeon ', '')

function PartLink({ p }: { p: Part }) {
  return (
    <a href={paths.hardwarePart(p.id)} onClick={onLinkClick(paths.hardwarePart(p.id))} className="hover:underline">
      {short(p)}
    </a>
  )
}

function Row({ v, task, need, result }: { v: Verdict; task: string; need: string; result: string }) {
  return (
    <li className="grid grid-cols-[1.2rem_minmax(0,1fr)] gap-x-1 py-1 border-t border-(--color-border-soft) first:border-t-0">
      <span className={`font-bold ${TONE[v]}`}>{MARK[v]}</span>
      <div>
        <div className="text-sm">
          <b>{task}</b> <span className="text-[11px] text-(--color-faint)">— {need}</span>
        </div>
        <div className="text-xs text-(--color-muted)">{result}</div>
      </div>
    </li>
  )
}

// ── AI ─────────────────────────────────────────────────────────────

/** 그래픽 메모리 급 — 로컬 AI 에서 '무엇을 올릴 수 있나'는 속도보다 이 값이 먼저 정한다 */
const VRAM_TIERS: { min: number; label: string; why: string }[] = [
  { min: 24, label: '24GB 이상', why: '큰 모델을 통째로 — 외부로 못 내보내는 문서를 다루는 사내 챗봇·연구용' },
  { min: 16, label: '16GB', why: '로컬 AI 를 제대로 시작하는 기본값 — 코딩 도우미에 여유, 이미지·작은 모델 미세조정까지' },
  { min: 12, label: '12GB', why: '코딩 도우미 크기(14B)를 통째로 올리는 최소선 — 게임이 주고 AI 는 곁들이는 사람' },
  { min: 0, label: '8GB 이하', why: '게임이 먼저, AI 는 맛보기 — 작은 모델(8B)·이미지 생성까지' },
]

const tierOfVram = (v: number) => VRAM_TIERS.find((t) => v >= t.min)!

export function AiUses({ data, gpu, ram }: { data: HwData; gpu: Part; ram?: Part }) {
  const b = data.bench
  const ramBw = ram ? Number(ram.specs.dual_bandwidth_gbs) || null : null
  const vram = Number(gpu.specs.vram_gb)
  const room = vram - b.llm.overhead_gb
  const m = (k: string) => b.llm.models.find((x) => x.key === k)
  const est = (x?: LlmModel) => (x ? estimateLlm(b, x, gpu, ramBw) : null)
  const v = (tps: number, fits = true): Verdict => (!fits || tps < b.llm.readable_tps ? (tps >= 2 ? 'ok' : 'bad') : 'good')
  const e8 = est(m('8b')), e14 = est(m('14b')), e27 = est(m('27b')), e32 = est(m('32b'))
  const img = estimateImageSec(b, gpu, data.parts)
  const ft = (k: string) => b.finetune.find((f) => f.key === k)
  const q8 = ft('qlora-8b'), q32 = ft('qlora-32b')
  const big = e32?.fits ? e32 : e27?.fits ? e27 : null
  const bigModel = e32?.fits ? m('32b') : m('27b')

  // 급별 카드 — 오늘 가격이 있는 현행 카드만
  const cards = data.parts
    .filter((p) => p.category === 'gpu' && p.status === 'current')
    .map((p) => ({ p, price: priceOf(p, data.prices), vram: Number(p.specs.vram_gb) }))
    .filter((x): x is { p: Part; price: number; vram: number } => x.price != null)
  const myTier = tierOfVram(vram)
  const tiers = [...VRAM_TIERS].reverse().map((t, i, all) => {
    const upper = all[i + 1]?.min ?? Infinity
    const xs = cards.filter((c) => c.vram >= t.min && c.vram < upper).sort((a, c) => a.price - c.price)
    // 급 안에서 VRAM 이 가장 큰 카드 기준(8GB 이하 급에 6GB 카드가 섞여 있다)
    const top = Math.max(t.min, ...xs.map((x) => x.vram))
    const fitMax = [...b.llm.models].reverse().find((x) => x.size_gb <= top - b.llm.overhead_gb)
    return { t, xs, fitMax, top }
  })
  const nextTier = tiers.find((x) => x.t.min > myTier.min && x.xs.length)
  const myPrice = priceOf(gpu, data.prices)

  return (
    <div className="flex flex-col gap-3 border-t border-(--color-border-soft) pt-3">
      <div>
        <h3 className="text-sm font-semibold mb-1">이 카드로 실제 하는 일</h3>
        <ul className="flex flex-col">
          {e8 && (
            <Row
              v={e8.tps >= b.llm.comfortable_tps ? 'good' : v(e8.tps, e8.fits)}
              task="코드 자동완성 · 문서 요약·번역"
              need={`8B 모델 · 자동완성은 ${b.llm.comfortable_tps}토큰/초는 나와야 기다림 없이 뜬다`}
              result={`${fmtTps(e8.tps)}토큰/초 — ${e8.tps >= b.llm.comfortable_tps ? '타이핑을 따라온다' : e8.tps >= b.llm.readable_tps ? '요약·번역은 되지만 자동완성은 굼뜨다' : '느리다'}`}
            />
          )}
          {e14 && (
            <Row
              v={v(e14.tps, e14.fits)}
              task="코딩 도우미 · 코드 리뷰 질문"
              need="14B 모델 — 코딩 질문에 쓸 만해지는 크기"
              result={
                e14.fits
                  ? `${fmtTps(e14.tps)}토큰/초 · 메모리 여유 ${Math.max(0, room - (m('14b')?.size_gb ?? 0)).toFixed(1)}GB — 여유가 클수록 긴 파일·긴 대화를 넣을 수 있다`
                  : `${fmtTps(e14.tps)}토큰/초 — ${e14.note}`
              }
            />
          )}
          {(e27 || e32) && (
            <Row
              v={big ? v(big.tps) : 'bad'}
              task="사내 챗봇 · 외부 API 를 못 쓰는 문서"
              need="27~32B 모델 — 일상 대화가 상용 모델에 가까워지는 크기"
              result={
                big
                  ? `${bigModel?.name} 를 통째로 올려 ${fmtTps(big.tps)}토큰/초`
                  : `그래픽 메모리 ${vram}GB 로는 안 들어간다(27B 는 ${m('27b')?.size_gb}GB) — 넘친 부분을 시스템 메모리에서 읽어 ${fmtTps(e27?.tps ?? 0)}토큰/초로 떨어진다`
              }
            />
          )}
          <Row
            v={img == null ? 'bad' : img <= 10 ? 'good' : 'ok'}
            task="이미지 시안 100장"
            need={`SDXL 1024×1024 · VRAM ${b.image.min_vram_gb}GB 이상`}
            result={img == null ? '못 돌린다' : `한 장 ${img.toFixed(1)}초 — 100장이면 약 ${Math.ceil((img * 100) / 60)}분`}
          />
          {q8 && (
            <Row
              v={vram >= q8.vram_gb ? 'good' : 'bad'}
              task="내 데이터로 모델 길들이기"
              need={`${q8.name} ${q8.vram_gb}GB${q32 ? ` · ${q32.name} ${q32.vram_gb}GB` : ''}`}
              result={
                q32 && vram >= q32.vram_gb
                  ? '32B 까지 한 장으로 된다'
                  : vram >= q8.vram_gb
                    ? `8B 는 된다. 32B 는 ${q32?.vram_gb}GB 가 필요하다`
                    : `그래픽 메모리 ${vram}GB 로는 8B 도 모자란다`
              }
            />
          )}
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold">이럴 때 이 급을 산다</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          로컬 AI 는 속도보다 <b>그래픽 메모리(VRAM)</b>가 먼저다 — 모델이 안 들어가면 빠른 카드도 느려진다. 급 구분은 우리 것이고 값은 오늘 최저가다.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {tiers
            .filter((x) => x.xs.length)
            .map(({ t, xs, fitMax, top }) => {
              const mine = t === myTier
              return (
                <div key={t.label} className={`rounded-md p-2.5 text-xs ${mine ? 'border-2 border-(--color-accent) bg-(--color-accent)/5' : 'border border-(--color-border-soft)'}`}>
                  <div className="flex items-baseline gap-2">
                    <b className="text-sm">{t.label}</b>
                    {mine && <span className="text-[10px] px-1 rounded bg-(--color-accent) text-(--color-on-accent)">지금 고른 급</span>}
                  </div>
                  <p className="text-(--color-muted) mt-0.5">{t.why}</p>
                  <p className="mt-1">
                    통째로 올라가는 가장 큰 모델: <b>{fitMax?.name ?? '없음'}</b>
                    <span className="text-(--color-faint)"> ({top}GB 카드 기준)</span>
                  </p>
                  <p className="mt-1">
                    {xs.slice(0, 4).map((x, i) => (
                      <span key={x.p.id}>
                        {i > 0 && ' · '}
                        <PartLink p={x.p} /> <span className="text-(--color-muted) tabular-nums">{won(x.price)}</span>
                        {x.p.specs.stack !== 'CUDA' && <span className="text-(--color-faint)">({String(x.p.specs.stack)})</span>}
                      </span>
                    ))}
                  </p>
                </div>
              )
            })}
        </div>
        {nextTier && (
          <p className="text-xs mt-2">
            <span className="text-(--color-muted)">한 급 위({nextTier.t.label})로 가면: </span>
            가장 싼 <PartLink p={nextTier.xs[0].p} /> 가 {won(nextTier.xs[0].price)}
            {myPrice != null && ` (지금보다 ${nextTier.xs[0].price >= myPrice ? '+' : '−'}${won(Math.abs(nextTier.xs[0].price - myPrice))})`} — {nextTier.fitMax?.name ?? '더 큰 모델'} 까지 통째로 올라간다.
          </p>
        )}
        <p className="text-[11px] text-(--color-faint) mt-1">
          AMD(ROCm)·인텔(oneAPI)은 같은 VRAM 을 더 싸게 주지만 소프트웨어 보정을 {b.llm.stack_factor.ROCm}·{b.llm.stack_factor.oneAPI} 로 잡았다(CUDA = 1). 쓰려는 도구가 그 카드를 지원하는지 먼저 확인한다.
        </p>
      </div>
    </div>
  )
}

// ── 개발 ────────────────────────────────────────────────────────────

const BUILDS_PER_DAY = 10

/** 개발 용도별 CPU 급 — 멀티 지수(9950X = 100) 문턱. X3D 는 게임 겸용으로 따로 본다 */
const DEV_TIERS: { key: string; label: string; why: string; pick: (p: Part) => boolean }[] = [
  { key: 'big', label: '대형 빌드 · 컴파일이 일인 사람', why: 'C++·게임 엔진·안드로이드 풀 빌드, 로컬에서 여러 서비스를 한꺼번에 — 기다리는 시간이 곧 돈이다', pick: (p) => (p.perf.multi ?? 0) >= 70 && !/X3D/.test(p.name) },
  { key: 'mid', label: '일반 백엔드 · 풀스택', why: 'IDE 두어 개 + 도커 몇 개. 풀 빌드는 가끔이고 대부분 증분 빌드다', pick: (p) => (p.perf.multi ?? 0) >= 40 && (p.perf.multi ?? 0) < 70 && !/X3D/.test(p.name) },
  { key: 'game', label: '게임도 같이 하는 개발자', why: 'X3D — 게임 지수가 가장 높고 빌드는 중간. 하나로 둘 다 할 때', pick: (p) => /X3D/.test(p.name) },
  { key: 'light', label: '웹 · 가벼운 개발 · 공부', why: '프론트엔드·스크립트·강의 실습. 풀 빌드가 드물어 6코어로 충분하다', pick: (p) => (p.perf.multi ?? 0) < 40 && !/X3D/.test(p.name) },
]

export function DevUses({ data, cpu, ram }: { data: HwData; cpu: Part; ram?: Part }) {
  const b = data.bench
  const mins = estimateBuildMin(b, cpu)
  const gb = ram ? Number(ram.specs.capacity_gb) * 2 : null
  const cpus = data.parts
    .filter((p) => p.category === 'cpu' && p.status === 'current')
    .map((p) => ({ p, price: priceOf(p, data.prices), min: estimateBuildMin(b, p) }))
    .filter((x): x is { p: Part; price: number; min: number } => x.price != null)
  const fastest = [...cpus].sort((a, c) => a.min - c.min)[0]
  const myPrice = priceOf(cpu, data.prices)
  // 한 단계 위 — 빌드가 20% 넘게 줄어드는 CPU 중 가장 싼 것
  const step = cpus.filter((x) => x.min <= mins * 0.8).sort((a, c) => a.price - c.price)[0]
  const myTier = DEV_TIERS.find((t) => t.pick(cpu))
  const wait = (m: number) => m * BUILDS_PER_DAY

  return (
    <div className="flex flex-col gap-3 border-t border-(--color-border-soft) pt-3">
      <div>
        <h3 className="text-sm font-semibold mb-1">하루에 기다리는 시간</h3>
        <ul className="flex flex-col">
          <Row
            v={mins <= 15 ? 'good' : mins <= 30 ? 'ok' : 'bad'}
            task={`풀 빌드 하루 ${BUILDS_PER_DAY}번`}
            need="브랜치를 바꾸거나 의존성을 올릴 때마다 한 번"
            result={`한 번 약 ${fmtMin(mins)}분 — 하루 ${Math.round(wait(mins))}분을 빌드를 기다린다`}
          />
          {fastest && fastest.p.id !== cpu.id && (
            <Row
              v="ok"
              task={`가장 빠른 ${short(fastest.p)} 였다면`}
              need={`${won(fastest.price)}${myPrice != null ? ` · 지금보다 +${won(Math.max(0, fastest.price - myPrice))}` : ''}`}
              result={`한 번 ${fmtMin(fastest.min)}분 — 하루 ${Math.round(wait(mins) - wait(fastest.min))}분, 한 달(20일) 약 ${Math.round(((wait(mins) - wait(fastest.min)) * 20) / 60)}시간을 아낀다`}
            />
          )}
          <Row
            v={gb == null ? 'ok' : gb >= 32 ? 'good' : 'bad'}
            task="도커 · 로컬 쿠버네티스 · 에뮬레이터를 같이"
            need="빌드와 동시에 띄우면 메모리가 먼저 막힌다"
            result={
              gb == null
                ? '메모리를 고르면 나온다'
                : gb >= 64
                  ? `${gb}GB — 컨테이너 10개 이상 + 안드로이드 에뮬레이터까지 여유`
                  : gb >= 32
                    ? `${gb}GB — 컨테이너 몇 개 + 에뮬레이터 하나. 로컬 쿠버네티스를 늘 띄우면 64GB`
                    : `${gb}GB — 도커를 여러 개 띄우면 스왑이 난다. 개발용이면 32GB 부터`
            }
          />
        </ul>
        {step && step.p.id !== cpu.id && (
          <p className="text-xs mt-1">
            <span className="text-(--color-muted)">한 단계 위: </span>
            <PartLink p={step.p} /> — 빌드 {fmtMin(mins)}분 → {fmtMin(step.min)}분(하루 {Math.round(wait(mins) - wait(step.min))}분 절약) ·{' '}
            {won(step.price)}
            {myPrice != null && ` (지금보다 ${step.price >= myPrice ? '+' : '−'}${won(Math.abs(step.price - myPrice))})`}
            {step.p.specs.socket !== cpu.specs.socket && <span className="text-(--color-amber-400)"> · 소켓이 달라 보드도 바꿔야 한다</span>}
          </p>
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold">이럴 때 이 CPU 를 산다</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          빌드는 코어 수(멀티 지수)에, 게임은 캐시·싱글 성능(게임 지수)에 달렸다. 구분 문턱(멀티 지수 40·70)은 우리 것이고 값은 오늘 정품 최저가다.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {DEV_TIERS.map((t) => {
            const xs = cpus.filter((x) => t.pick(x.p)).sort((a, c) => a.price - c.price)
            if (!xs.length) return null
            const mine = t === myTier
            return (
              <div key={t.key} className={`rounded-md p-2.5 text-xs ${mine ? 'border-2 border-(--color-accent) bg-(--color-accent)/5' : 'border border-(--color-border-soft)'}`}>
                <div className="flex items-baseline gap-2">
                  <b className="text-sm">{t.label}</b>
                  {mine && <span className="text-[10px] px-1 rounded bg-(--color-accent) text-(--color-on-accent)">지금 고른 CPU</span>}
                </div>
                <p className="text-(--color-muted) mt-0.5">{t.why}</p>
                <ul className="mt-1 flex flex-col gap-0.5">
                  {xs.slice(0, 4).map((x) => (
                    <li key={x.p.id} className="flex flex-wrap gap-x-2 tabular-nums">
                      <PartLink p={x.p} />
                      <span className="text-(--color-muted)">빌드 {fmtMin(x.min)}분 · 게임 지수 {x.p.perf.index}</span>
                      <span className="ml-auto">{won(x.price)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
        <p className="text-[11px] text-(--color-faint) mt-1">
          빌드 시간은 '{b.dev.name}' 을 {b.dev.anchor_minutes}분(9950X)으로 둔 추정이다 — {b.dev.model}
        </p>
      </div>
    </div>
  )
}

// ── 영상 편집 ──────────────────────────────────────────────────────
//
// 게임·AI 와 달리 여기 점수는 추정식이 아니라 Puget 의 DaVinci Resolve 실측(사용자 제출)이다.
// 영상 편집에서 '되나 안 되나'를 먼저 가르는 건 속도보다 코덱이다 — 카메라 원본(10비트 4:2:2)을
// 그래픽카드가 못 풀면 CPU 가 풀고, 그러면 빠른 카드도 4K 타임라인이 끊긴다.
// 효과 점수 문턱(55·100)은 우리가 정한 구분이다.

const VIDEO_TIERS: { key: string; label: string; why: string; min: number }[] = [
  { key: 'pro', label: '편집이 본업 · 외주', why: '4K 멀티캠, 노이즈 제거·색보정 노드를 여러 겹 — 효과를 쌓아도 재생이 안 멈춘다', min: 100 },
  { key: 'mid', label: '4K 유튜브 · 브이로그', why: '컷 편집 + 가벼운 색보정·자막. 무거운 효과는 렌더 캐시를 걸고 본다', min: 55 },
  { key: 'entry', label: 'FHD 편집 · 컷 위주', why: '자르고 붙이고 자막. 4K 는 프록시(가벼운 사본)를 만들어 편집한다', min: 0 },
]

export function VideoSim({ data, gpu, cpu, ram }: { data: HwData; gpu: Part; cpu?: Part; ram?: Part }) {
  const vb = data.bench.video
  if (!vb) return null
  const s: VideoScore | undefined = vb.gpu[gpu.id]
  const vram = Number(gpu.specs.vram_gb)
  const gb = ram ? Number(ram.specs.capacity_gb) * 2 : null
  // 인텔 내장 그래픽(Quick Sync)은 HEVC 4:2:2 를 푼다 — 라이젠 내장 그래픽은 못 푼다
  const qsv = !!cpu && cpu.maker === 'Intel' && !!cpu.specs.igpu
  const dec = new Set<string>([...(s?.dec422 ?? []), ...(qsv ? ['hevc'] : [])])
  const decV: Verdict = dec.has('h264') && dec.has('hevc') ? 'good' : dec.size ? 'ok' : 'bad'
  const pct = s ? Math.round((s.effects / vb.effects_top) * 100) : null
  const effV: Verdict = s == null ? 'ok' : s.effects >= 100 ? 'good' : s.effects >= 55 ? 'ok' : 'bad'
  const cards = data.parts
    .filter((p) => p.category === 'gpu' && p.status === 'current' && vb.gpu[p.id])
    .map((p) => ({ p, price: priceOf(p, data.prices), v: vb.gpu[p.id] }))
    .filter((x): x is { p: Part; price: number; v: VideoScore } => x.price != null)
  const myTier = s ? VIDEO_TIERS.find((t) => s.effects >= t.min) : undefined
  const myPrice = priceOf(gpu, data.prices)
  // 한 단계 위 — 효과 점수가 25% 넘게 오르는 카드 중 가장 싼 것
  const step = s ? cards.filter((x) => x.v.effects >= s.effects * 1.25).sort((a, c) => a.price - c.price)[0] : undefined

  return (
    <div className="rounded-lg border border-(--color-border) bg-(--color-panel) p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-base font-bold">영상 편집은 얼마나 되나</h2>
        <span className="text-xs text-(--color-muted)">{vb.name} · 추정이 아니라 실측 점수</span>
      </div>
      <div className="grid sm:grid-cols-3 gap-3 text-sm">
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">효과 점수(색보정·노이즈 제거)</div>
          <div className="text-xl font-bold tabular-nums">{s ? s.effects.toFixed(0) : '측정 없음'}</div>
          {pct != null && (
            <>
              <div className="h-1.5 rounded bg-(--color-border-soft) mt-1">
                <div className="h-full rounded bg-(--color-accent)/70" style={{ width: `${Math.min(100, pct)}%` }} />
              </div>
              <div className="text-[11px] text-(--color-faint) mt-0.5">
                RTX 5090({vb.effects_top.toFixed(0)})의 {pct}%
              </div>
            </>
          )}
        </div>
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">카메라 원본 재생(LongGOP)</div>
          <div className="text-xl font-bold tabular-nums">{s ? s.longgop.toFixed(0) : '—'}</div>
          <div className="text-[11px] text-(--color-faint)">H.264·HEVC 원본을 편집하며 재생하는 힘</div>
        </div>
        <div className="rounded-lg bg-(--color-band) p-3">
          <div className="text-[11px] text-(--color-muted)">총점(Standard)</div>
          <div className="text-xl font-bold tabular-nums">{s ? Math.round(s.overall).toLocaleString() : '—'}</div>
          <div className="text-[11px] text-(--color-faint)">제출자마다 CPU 가 달라 CPU 몫이 섞여 있다</div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1">이 조합으로 실제 하는 일</h3>
        <ul className="flex flex-col">
          <Row
            v={decV}
            task="미러리스 카메라 4K 원본을 바로 편집"
            need="소니·캐논·파나소닉의 10비트 4:2:2 — 하드웨어로 못 풀면 CPU 가 푼다"
            result={
              decV === 'good'
                ? `${short(gpu)} 가 H.264·HEVC 4:2:2 를 둘 다 푼다 — 프록시 없이 원본으로 편집한다`
                : decV === 'ok'
                  ? `HEVC 4:2:2 는 인텔 내장 그래픽(Quick Sync)이 푼다. H.264 4:2:2 는 CPU 가 풀어 끊길 수 있다 — 카메라를 HEVC 로 찍거나 프록시를 만든다`
                  : `${short(gpu)} 도 ${cpu ? short(cpu) : 'CPU'} 내장 그래픽도 4:2:2 를 하드웨어로 못 푼다 — 4K 재생이 끊기기 쉽다. 프록시를 만들어 편집하거나 RTX 50 · 인텔 내장 그래픽 CPU 로 간다`
            }
          />
          <Row
            v={effV}
            task="색보정 · 노이즈 제거 · 효과 쌓기"
            need="효과는 거의 그래픽카드가 한다 — 효과 점수 100 이상이면 겹겹이 쌓아도 재생한다(우리 문턱)"
            result={
              s == null
                ? '이 카드는 2.x 판 실측이 없다'
                : effV === 'good'
                  ? `효과 점수 ${s.effects.toFixed(0)} — 노드를 여러 겹 쌓아도 실시간에 가깝다`
                  : effV === 'ok'
                    ? `효과 점수 ${s.effects.toFixed(0)} — 가벼운 색보정은 실시간, 노이즈 제거는 렌더 캐시를 건다`
                    : `효과 점수 ${s.effects.toFixed(0)} — 효과를 두세 개 넘게 걸면 재생이 멈춘다`
            }
          />
          <Row
            v={vram >= vb.vram_min_gb.uhd ? 'good' : vram >= vb.vram_min_gb.fhd ? 'ok' : 'bad'}
            task="타임라인 해상도"
            need={`그래픽 메모리 최소 — FHD ${vb.vram_min_gb.fhd}GB · 4K ${vb.vram_min_gb.uhd}GB · 6K·8K ${vb.vram_min_gb['8k']}GB (Puget 권장)`}
            result={
              vram >= vb.vram_min_gb['8k']
                ? `${vram}GB — 6K·8K 타임라인까지`
                : vram >= vb.vram_min_gb.uhd
                  ? `${vram}GB — 4K 타임라인. 6K·8K 는 ${vb.vram_min_gb['8k']}GB 부터`
                  : vram >= vb.vram_min_gb.fhd
                    ? `${vram}GB — FHD 까지. 4K 에 효과를 쌓으면 'GPU 메모리 가득' 오류가 난다`
                    : `${vram}GB — FHD 최소(${vb.vram_min_gb.fhd}GB)에도 못 미친다`
            }
          />
          <Row
            v={gb == null ? 'ok' : gb >= vb.ram_min_gb.uhd ? 'good' : gb >= vb.ram_min_gb.fhd ? 'ok' : 'bad'}
            task="메모리"
            need={`Puget 최소 — FHD ${vb.ram_min_gb.fhd}GB · 4K ${vb.ram_min_gb.uhd}GB · 6K ${vb.ram_min_gb['6k']}GB`}
            result={
              gb == null
                ? '메모리를 고르면 나온다'
                : gb >= vb.ram_min_gb.uhd
                  ? `${gb}GB — 4K 권장치를 채운다`
                  : gb >= vb.ram_min_gb.fhd
                    ? `${gb}GB — 4K 편집은 되지만 Puget 권장(${vb.ram_min_gb.uhd}GB)보다 적다. 긴 타임라인·퓨전에서 먼저 막힌다`
                    : `${gb}GB — 편집 프로그램과 캐시가 메모리를 다 쓴다. 영상 편집이면 ${vb.ram_min_gb.fhd}GB 부터`
            }
          />
          {s && (
            <Row
              v={s.nvenc != null && s.nvenc >= 2 ? 'good' : 'ok'}
              task="내보내기(인코딩)"
              need="하드웨어 인코더가 여럿이면 한 파일을 나눠 굽는다"
              result={[
                s.nvenc != null ? `NVENC ${s.nvenc}개` : '하드웨어 인코더(AMD VCN)',
                s.av1_enc ? 'AV1 인코딩 됨' : 'AV1 인코딩 안 됨',
                s.dec422.length ? '4:2:2 로도 내보낸다' : '4:2:2 인코딩은 CPU',
              ].join(' · ')}
            />
          )}
        </ul>
      </div>

      <div>
        <h3 className="text-sm font-semibold">이럴 때 이 급을 산다</h3>
        <p className="text-[11px] text-(--color-muted) mb-1">
          효과 점수로 나눴다(문턱 55·100 은 우리 것). <b>4:2:2</b> 는 카메라 원본을 하드웨어로 푸는 카드다. 값은 오늘 최저가.
        </p>
        <div className="grid gap-2 sm:grid-cols-3">
          {VIDEO_TIERS.map((t, i) => {
            const upper = VIDEO_TIERS[i - 1]?.min ?? Infinity
            const xs = cards.filter((x) => x.v.effects >= t.min && x.v.effects < upper).sort((a, c) => a.price - c.price)
            if (!xs.length) return null
            const mine = t === myTier
            return (
              <div key={t.key} className={`rounded-md p-2.5 text-xs ${mine ? 'border-2 border-(--color-accent) bg-(--color-accent)/5' : 'border border-(--color-border-soft)'}`}>
                <div className="flex items-baseline gap-2">
                  <b className="text-sm">{t.label}</b>
                  {mine && <span className="text-[10px] px-1 rounded bg-(--color-accent) text-(--color-on-accent)">지금 고른 급</span>}
                </div>
                <p className="text-(--color-muted) mt-0.5">{t.why}</p>
                <ul className="mt-1 flex flex-col gap-0.5">
                  {xs.slice(0, 4).map((x) => (
                    <li key={x.p.id} className="flex flex-wrap gap-x-2 tabular-nums">
                      <PartLink p={x.p} />
                      <span className="text-(--color-muted)">
                        효과 {x.v.effects.toFixed(0)} · {String(x.p.specs.vram_gb)}GB{x.v.dec422.length ? ' · 4:2:2' : ''}
                      </span>
                      <span className="ml-auto">{won(x.price)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
        {s && step && (
          <p className="text-xs mt-2">
            <span className="text-(--color-muted)">효과가 25% 넘게 오르는 가장 싼 카드: </span>
            <PartLink p={step.p} /> — 효과 {s.effects.toFixed(0)} → {step.v.effects.toFixed(0)} · {won(step.price)}
            {myPrice != null && ` (지금보다 ${step.price >= myPrice ? '+' : '−'}${won(Math.abs(step.price - myPrice))})`}
          </p>
        )}
      </div>

      <details className="text-xs text-(--color-muted)">
        <summary className="cursor-pointer">어디서 온 숫자인가</summary>
        <p className="mt-1">{vb.model}</p>
        {s?.note && (
          <p className="mt-1">
            {short(gpu)}: {s.note}
          </p>
        )}
        {vb.gpu_note && <p className="mt-1">{vb.gpu_note}</p>}
        <p className="mt-1">윈도우에서 하드웨어 H.264·HEVC 디코딩은 Resolve 유료판(Studio)에서 켜진다 — 무료판은 CPU 가 푼다.</p>
        <ul className="mt-1 flex flex-col gap-0.5">
          {s && (
            <li>
              <a href={s.src} target="_blank" rel="noreferrer" className="hover:underline">
                이 카드의 Puget 결과 비교 페이지
              </a>
            </li>
          )}
          {vb.sources.map((x) => (
            <li key={x.url}>
              <a href={x.url} target="_blank" rel="noreferrer" className="hover:underline">
                {x.title}
              </a>
            </li>
          ))}
        </ul>
      </details>
    </div>
  )
}
