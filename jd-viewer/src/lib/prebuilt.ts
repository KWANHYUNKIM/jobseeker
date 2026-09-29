import { useEffect, useState } from 'react'
import { checkBuild, estimateBuildMin, estimateFps, estimateLlm, priceOf, systemWatts, tierOf, type Build, type HwData, type Part } from './hardware'

// 완제품 조립PC 분석 — '누가 설계해 파는 조립PC' 가 왜 잘 만들어졌나 / 가성비가 왜 좋은가.
//
// 데이터: public/hardware/prebuilt.json — catch_capture/crawlers/crawl_prebuilt.py 가 매일 쌓는다.
// 구성(comp)은 상품 페이지의 부품 모델명만 뽑은 구조이고, mapped 는 그것을 우리 부품 목록에 이은 것이다.
//
// 분석은 전부 우리 데이터로 한다(리뷰 글은 싣지 않는다 — 별점·리뷰 수만, 글은 원문 링크로):
//   부품값 합계  — 같은 날 우리가 받은 부품 최저가로 다시 맞춘 값. 모르는 칸은 가정을 적고 채운다.
//   조립 프리미엄 — 완제품 가격 − 부품값 합계. 조립·검수·A/S·배송값이 여기 들어 있다.
//   균형·여유    — CPU 와 그래픽카드의 급, 파워 여유, 메모리·SSD 용량, 호환성 검사.
//   가성비 순위  — 같은 목록 안에서 '예상 QHD 게임 fps 1 당 가격'.

export interface Comp {
  cpu: string | null
  gpu: string | null
  chipset: string | null
  os: string | null
  psu_w: number | null
  ram_type: string | null
  ram_gb: number | null
  storage: string | null
  storage_gb: number | null
  vram_gb: number | null
  case: string | null
  purpose: string | null
}

export interface Prebuilt {
  key: string
  name: string
  price: number
  source: 'danawa' | 'naver'
  url: string
  brand?: string | null
  mall?: string | null
  first_seen: string
  last_seen: string
  history: { d: string; price: number }[]
  comp?: Comp
  mapped?: Partial<Record<'cpu' | 'gpu' | 'mainboard' | 'ram' | 'psu' | 'case' | 'gpu_assumed', string | null>>
  rating?: { avg: number; count: number } | null
  offer_count?: number | null
}

let cache: Promise<{ day: string | null; items: Prebuilt[] }> | null = null

export function usePrebuilt(): { day: string | null; items: Prebuilt[] } | null {
  const [d, setD] = useState<{ day: string | null; items: Prebuilt[] } | null>(null)
  useEffect(() => {
    cache ??= fetch('/hardware/prebuilt.json')
      .then((r) => (r.ok ? r.json() : { items: {} }))
      .then((j: { day?: string; items?: Record<string, Omit<Prebuilt, 'key'>> }) => ({
        day: j.day ?? null,
        items: Object.entries(j.items ?? {}).map(([key, v]) => ({ key, ...v }) as Prebuilt),
      }))
      .catch(() => ({ day: null, items: [] }))
    let alive = true
    cache.then((x) => alive && setD(x))
    return () => {
      alive = false
    }
  }, [])
  return d
}

export interface CostLine {
  label: string
  part: Part | null
  price: number | null
  note?: string
}

export interface Analysis {
  lines: CostLine[]
  sum: number | null
  premium: number | null
  premiumPct: number | null
  /** 남기는 돈이 판매가에서 차지하는 비율(%) — 마진율 */
  marginPct: number | null
  unknown: string[]
  cpu: Part | null
  gpu: Part | null
  qhdFps: number | null
  good: string[]
  bad: string[]
  errors: string[]
}

const cheapestPerGb = (data: HwData, cat: 'ssd' | 'ram') => {
  const xs = data.parts
    .filter((p) => p.category === cat)
    .map((p) => {
      const pr = priceOf(p, data.prices)
      const gb = Number(p.specs.capacity_gb)
      return pr && gb ? { p, perGb: pr / gb } : null
    })
    .filter((x): x is { p: Part; perGb: number } => !!x)
  return xs
}

export function analyze(item: Prebuilt, data: HwData): Analysis {
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const m = item.mapped ?? {}
  const c = item.comp
  const get = (id?: string | null) => (id ? (byId.get(id) ?? null) : null)
  const cpu = get(m.cpu), gpu = get(m.gpu), mb = get(m.mainboard), ram = get(m.ram), psu = get(m.psu), cs = get(m.case)
  const unknown: string[] = []
  const lines: CostLine[] = []
  const add = (label: string, part: Part | null, price: number | null, note?: string) => lines.push({ label, part, price, note })

  add('CPU', cpu, cpu ? priceOf(cpu, data.prices) : null, cpu ? '정품 최저가' : undefined)
  if (!cpu && c?.cpu) unknown.push(`CPU '${c.cpu}'`)
  const integrated = !!c?.gpu && c.gpu.includes('내장')
  if (!integrated) {
    add('그래픽카드', gpu, gpu ? priceOf(gpu, data.prices) : null, m.gpu_assumed ?? undefined)
    if (!gpu && c?.gpu) unknown.push(`그래픽카드 '${c.gpu}'`)
  }
  add('메인보드', mb, mb ? priceOf(mb, data.prices) : null, mb ? '그 칩셋의 가장 싼 보드' : c?.chipset ? `'${c.chipset}' 칩셋 — 목록에 없음` : '표기 없음')
  if (ram) add('메모리', ram, (priceOf(ram, data.prices) ?? 0) * 2, '두 장')
  else if (c?.ram_gb && c.ram_type) {
    const per = cheapestPerGb(data, 'ram').filter((x) => x.p.specs.type === c.ram_type).sort((a, b) => a.perGb - b.perGb)[0]
    add('메모리', null, per ? Math.round(per.perGb * c.ram_gb) : null, per ? `${c.ram_type} ${c.ram_gb}GB — GB당 최저 단가로 추정` : undefined)
  }
  if (c?.storage_gb) {
    const per = cheapestPerGb(data, 'ssd').sort((a, b) => a.perGb - b.perGb)[0]
    add('SSD', null, per ? Math.round(per.perGb * c.storage_gb) : null, `${c.storage_gb >= 1000 ? c.storage_gb / 1000 + 'TB' : c.storage_gb + 'GB'} — GB당 최저 단가로 추정`)
  }
  const psuPart = psu ?? (c?.psu_w ? [...data.parts.filter((p) => p.category === 'psu')].sort((a, b) => Math.abs(Number(a.specs.watt) - c.psu_w!) - Math.abs(Number(b.specs.watt) - c.psu_w!))[0] : null)
  if (psuPart) add('파워', psuPart, priceOf(psuPart, data.prices), psu ? undefined : `${c?.psu_w}W — 가장 가까운 급으로 추정`)
  const casePart = cs ?? get('case-atx-mid')
  add('케이스', casePart, casePart ? priceOf(casePart, data.prices) : null, cs ? '급의 가운데 값' : '표기 없음 — 미들타워로 가정')
  const cooler = get('cooler-air-single')
  add('CPU 쿨러', cooler, cooler ? priceOf(cooler, data.prices) : null, '표기 없음 — 싱글타워 공랭으로 가정')

  const known = lines.filter((l) => l.price != null)
  const essentialMissing = !cpu || (!integrated && !gpu)
  const sum = essentialMissing ? null : known.reduce((s, l) => s + (l.price ?? 0), 0)
  const premium = sum != null ? item.price - sum : null
  const premiumPct = sum ? (premium! / sum) * 100 : null
  const marginPct = sum != null ? (premium! / item.price) * 100 : null

  // 호환성 — 판매 구성이 우리 검사에 걸리면 표기가 잘못됐거나 정말 문제가 있는 것이다
  const build: Build = { cpu: cpu?.id, gpu: gpu?.id, mainboard: mb?.id, ram: ram?.id, psu: psu?.id }
  const errors = checkBuild(build, data.parts).filter((x) => x.level === 'error').map((x) => x.text)

  const games = data.bench.games
  // CPU 를 모르면 CPU 천장을 못 재서 fps 가 부풀려진다 — 계산하지 않는다(순위에서도 빠진다).
  const qhdFps = gpu && cpu ? Math.round(games.reduce((s, g) => s + estimateFps(g, 'qhd', gpu, cpu).fps, 0) / games.length) : null

  const good: string[] = []
  const bad: string[] = []
  if (premiumPct != null) {
    if (premiumPct <= 5) good.push(`원가와 거의 같다(원가 대비 +${Math.round(premiumPct)}%) — 조립·검수값을 거의 안 받는 셈이다`)
    else if (premiumPct <= 15) good.push(`남기는 돈 원가 대비 +${Math.round(premiumPct)}% — 조립·검수·A/S 값으로 흔한 범위다`)
    else if (premiumPct >= 25) bad.push(`부품을 따로 사면 약 ${Math.round(premium! / 10000)}만원(${Math.round(premiumPct)}%) 싸다`)
    else bad.push(`남기는 돈 원가 대비 +${Math.round(premiumPct)}% — 조금 비싸다`)
  }
  if (cpu && gpu) {
    const ct = tierOf(cpu, data.categories)?.tier, gt = tierOf(gpu, data.categories)?.tier
    const cpuBound = games.filter((g) => estimateFps(g, 'qhd', gpu, cpu).bound === 'cpu').length
    if (gpu.perf.index >= 65 && cpu.perf.index < 75) bad.push(`CPU(${ct})가 그래픽카드(${gt})를 못 따라간다 — QHD 게임 ${cpuBound}/${games.length}개에서 CPU 가 천장이다`)
    else if (gpu.perf.index < 40 && cpu.perf.index >= 90) bad.push(`CPU(${ct})에 돈이 쏠렸다 — 게임 성능은 그래픽카드(${gt})가 정한다`)
    else good.push(`CPU(${ct}) · 그래픽카드(${gt}) 균형이 맞다 — ${cpuBound ? `QHD 게임 ${games.length}개 중 CPU 가 천장인 건 ${cpuBound}개(가벼운 e스포츠)뿐이다` : `QHD 게임 ${games.length}개 모두 그래픽카드가 먼저 한계에 닿는다`}`)
  }
  if (c?.psu_w && (cpu || gpu)) {
    const need = systemWatts(cpu ?? undefined, gpu ?? undefined)
    const r = c.psu_w / need
    if (r >= 1.4) good.push(`파워 ${c.psu_w}W — 최대 소비 약 ${need}W 에 여유 ${Math.round((r - 1) * 100)}%`)
    else if (r < 1.15) bad.push(`파워 ${c.psu_w}W 가 최대 소비 약 ${need}W 에 빠듯하다`)
  }
  if (c?.ram_gb) {
    if (c.ram_gb >= 32) good.push(`메모리 ${c.ram_gb}GB — 게임과 개발(IDE·도커)을 같이 해도 넉넉하다`)
    else bad.push(`메모리 ${c.ram_gb}GB — 게임은 되지만 개발·로컬 AI 에는 모자란다(32GB 권장)`)
  }
  if (c?.storage_gb && c.storage_gb < 1000) bad.push(`SSD ${c.storage_gb}GB — 최신 게임 몇 개면 찬다`)
  if (mb && cpu && mb.perf.index < 50 && cpu.perf.index >= 85) bad.push(`보급형 칩셋(${mb.name})에 상위 CPU — 전원부·확장이 아쉬울 수 있다`)
  if (c?.os && c.os.includes('미포함')) bad.push('윈도우가 없다 — 따로 사거나 설치해야 한다')
  if (m.gpu_assumed) bad.push(`판매 표기에 그래픽 메모리 용량이 없다 — ${m.gpu_assumed}`)
  if (unknown.length) bad.push(`우리 부품 목록에 없는 부품이 있어 계산에서 뺐다: ${unknown.join(', ')}`)

  return { lines, sum, premium, premiumPct, marginPct, unknown, cpu, gpu, qhdFps, good, bad, errors }
}

/** 같은 목록 안에서 '예상 QHD 평균 fps 1 당 가격' 순위(낮을수록 싸게 먹힌다). 1 = 가장 가성비 좋음. */
export function valueRanks(items: Prebuilt[], data: HwData): Map<string, { rank: number; of: number; wonPerFps: number }> {
  const scored = items
    .map((it) => ({ it, a: analyze(it, data) }))
    .filter((x) => x.a.qhdFps)
    .map((x) => ({ key: x.it.key, wonPerFps: x.it.price / x.a.qhdFps! }))
    .sort((a, b) => a.wonPerFps - b.wonPerFps)
  return new Map(scored.map((s, i) => [s.key, { rank: i + 1, of: scored.length, wonPerFps: s.wonPerFps }]))
}

// ── 성능 우선 ────────────────────────────────────────────────────────
//
// 가성비는 '1fps 에 얼마'다. 그런데 일(사업)에 쓰는 기계는 돈보다 성능이 먼저인 때가 있다 —
// 렌더·빌드가 10분 줄면 사람 시간이 그만큼 산다. 그래서 가격은 보지 않고 용도별 성능만으로 줄 세운다.
// 같은 성능이면 싼 쪽이 위다(돈을 아예 안 보는 건 아니다 — 같은 값을 더 주고 살 이유는 없다).
//
//   게임 QHD · 4K  — 예상 평균 fps(bench.games, CPU 천장 포함)
//   로컬 AI        — 14B 언어 모델 생성 속도(토큰/초). 그래픽카드 메모리에 안 들어가면 급격히 느려진다
//   빌드 · 렌더    — 멀티 지수로 잰 풀 빌드 시간(분). 짧을수록 위
//
// 성능만 보면 놓치는 것 — '다음 단계'. 이보다 빠른 완제품 중 가장 싼 것과, 성능 몇 % 에 얼마를 더 내나.

export type PerfUse = 'game-qhd' | 'game-4k' | 'ai' | 'build'

export const PERF_USES: { key: PerfUse; label: string; unit: string; plain: string }[] = [
  { key: 'game-qhd', label: '게임 · QHD', unit: 'fps', plain: '예상 평균 fps (2560×1440 고옵션)' },
  { key: 'game-4k', label: '게임 · 4K', unit: 'fps', plain: '예상 평균 fps (3840×2160 고옵션)' },
  { key: 'ai', label: '로컬 AI', unit: '토큰/초', plain: '14B 언어 모델(코딩 도우미 급) 생성 속도' },
  { key: 'build', label: '빌드 · 렌더', unit: '분', plain: '대형 프로젝트 풀 빌드 시간 — 짧을수록 좋다' },
]

export interface PerfScore {
  /** 줄 세우는 값 — 클수록 좋다(빌드는 분이라 화면에는 display 를 쓴다) */
  score: number | null
  display: string
  /** 이 기계에서 이 일의 천장이 되는 부품 */
  bottleneck: string | null
  cpu: Part | null
  gpu: Part | null
  /** 구성표가 없어 상품 이름에서 CPU·그래픽카드를 읽었다 */
  fromName: boolean
}

// ── 상품 이름에서 부품 읽기 ──────────────────────────────────────────
//
// 크롤러가 상품 페이지 구성표(comp)를 아직 못 받은 완제품이 많다 — 그중에 9800X3D + 5080 같은
// 최상위 기계가 섞여 있어, 성능으로 줄 세우면 1위가 빠진다. 이름에는 대개 부품이 적혀 있다
// ("R7 9800X3D RTX5080 32GB"). 그래서 구성표가 없을 때만 이름에서 읽는다(화면에 그렇다고 적는다).
// 메모리 용량만 다른 칩(5060 Ti 8GB/16GB)은 이름의 '16GB' 가 시스템 메모리일 때가 많아 8GB 로 둔다.

let nameRules: { parts: Part[]; rules: { re: RegExp; part: Part }[] } | null = null

function rulesFor(parts: Part[]) {
  if (nameRules?.parts === parts) return nameRules.rules
  const loose = (t: string) => t.replace(/(\d)([A-Z])/g, '$1\\s*$2').replace(/([A-Z])(\d)/g, '$1\\s*$2')
  const rules: { re: RegExp; part: Part; len: number }[] = []
  for (const p of parts) {
    if (p.category !== 'gpu' && p.category !== 'cpu') continue
    if (p.category === 'gpu' && /-16$/.test(p.id)) continue
    const t = (
      p.category === 'gpu'
        ? p.name.replace(/^(GeForce RTX|Radeon RX|Arc)\s+/, '').replace(/\s*\d+GB$/, '')
        : p.name.replace(/^(Ryzen \d|Core Ultra \d|Core)\s+/, '').replace(/^i\d-/, '')
    )
      .toUpperCase()
      .replace(/\s+/g, '')
    // 265K 는 265KF(내장 그래픽만 끈 판)도 같은 성능으로 읽는다
    const tail = p.category === 'cpu' && t.endsWith('K') ? 'F?' : ''
    rules.push({ re: new RegExp(`(?<![0-9])${loose(t)}${tail}(?![0-9A-Z])`), part: p, len: t.length })
  }
  rules.sort((a, b) => b.len - a.len)
  nameRules = { parts, rules }
  return rules
}

export function partsFromName(name: string, parts: Part[]): { cpu: Part | null; gpu: Part | null } {
  const n = name.toUpperCase().replace(/[-_/]/g, ' ')
  const rules = rulesFor(parts)
  const find = (cat: 'cpu' | 'gpu') => rules.find((r) => r.part.category === cat && r.re.test(n))?.part ?? null
  return { cpu: find('cpu'), gpu: n.includes('내장') ? null : find('gpu') }
}

const avgFps = (data: HwData, res: 'qhd' | 'uhd', gpu: Part, cpu: Part) => {
  const gs = data.bench.games
  const es = gs.map((g) => estimateFps(g, res, gpu, cpu))
  return { fps: es.reduce((s, e) => s + e.fps, 0) / gs.length, cpuBound: es.filter((e) => e.bound === 'cpu').length, vramShort: es.filter((e) => e.vramShort > 0).length, n: gs.length }
}

export function perfOf(item: Prebuilt, data: HwData, use: PerfUse): PerfScore {
  const byId = new Map(data.parts.map((p) => [p.id, p]))
  const m = item.mapped ?? {}
  const hasComp = !!(item.comp?.cpu || item.comp?.gpu)
  const guess = hasComp ? { cpu: null, gpu: null } : partsFromName(item.name, data.parts)
  const cpu = (m.cpu ? byId.get(m.cpu) : null) ?? guess.cpu
  const integrated = !!item.comp?.gpu?.includes('내장')
  const gpu = (m.gpu ? byId.get(m.gpu) : null) ?? (integrated ? null : guess.gpu)
  const ram = m.ram ? (byId.get(m.ram) ?? null) : null
  const fromName = !hasComp && !!(guess.cpu || guess.gpu)
  const base = { cpu, gpu, fromName }
  const none = (why: string): PerfScore => ({ score: null, display: '—', bottleneck: why, ...base })
  if (use === 'game-qhd' || use === 'game-4k') {
    if (!gpu || !cpu) return none(!gpu ? '그래픽카드를 모른다(내장 그래픽이거나 목록에 없다)' : 'CPU 를 모른다')
    const r = avgFps(data, use === 'game-qhd' ? 'qhd' : 'uhd', gpu, cpu)
    const bottleneck =
      r.vramShort > r.n / 3
        ? `그래픽 메모리 ${gpu.specs.vram_gb}GB — ${r.n}개 중 ${r.vramShort}개 게임에서 모자라 프레임이 깎인다`
        : r.cpuBound > r.n / 2
          ? `CPU(${cpu.name}) — ${r.n}개 중 ${r.cpuBound}개 게임에서 CPU 가 천장이다. 그래픽카드를 올려도 안 는다`
          : `그래픽카드(${gpu.name}) — 성능을 올리려면 여기를 올린다`
    return { score: r.fps, display: `${Math.round(r.fps)} fps`, bottleneck, ...base }
  }
  if (use === 'ai') {
    if (!gpu) return none('그래픽카드를 모른다 — 내장 그래픽으로는 언어 모델이 사실상 안 돈다')
    const model = data.bench.llm.models.find((x) => x.key === '14b') ?? data.bench.llm.models[0]
    const e = estimateLlm(data.bench, model, gpu, ram ? Number(ram.specs.dual_bandwidth_gbs) || null : null)
    const vram = Number(gpu.specs.vram_gb ?? 0)
    const fitsMax = [...data.bench.llm.models].reverse().find((x) => x.size_gb <= vram - data.bench.llm.overhead_gb)
    return {
      score: e.tps,
      display: `${e.tps >= 10 ? Math.round(e.tps) : e.tps.toFixed(1)} 토큰/초`,
      bottleneck: e.fits
        ? `그래픽 메모리 ${vram}GB — 통째로 올릴 수 있는 가장 큰 모델은 ${fitsMax?.name ?? '없음'}`
        : `그래픽 메모리 ${vram}GB — 14B 가 다 안 들어가 ${e.note}`,
      ...base,
    }
  }
  if (!cpu) return none('CPU 를 모른다')
  const min = estimateBuildMin(data.bench, cpu)
  const gb = item.comp?.ram_gb
  return {
    score: -min,
    display: `약 ${min < 10 ? min.toFixed(1) : Math.round(min)}분`,
    bottleneck:
      gb && gb < 32
        ? `메모리 ${gb}GB — 병렬 빌드·도커를 같이 돌리면 모자란다(CPU 보다 먼저 막힌다)`
        : `CPU(${cpu.name}, 멀티 지수 ${cpu.perf.multi ?? cpu.perf.index}) — 빌드 시간은 코어 수에 거의 비례한다`,
    ...base,
  }
}

export interface PerfRank {
  rank: number
  of: number
  score: PerfScore
  /** 1위 대비 성능(%) */
  rel: number
  /** 이보다 빠른 완제품 중 가장 싼 것 — 한 단계 올리는 데 드는 돈 */
  next: { key: string; name: string; gainPct: number; extra: number } | null
}

export function perfRanks(items: Prebuilt[], data: HwData, use: PerfUse): Map<string, PerfRank> {
  const xs = items
    .map((it) => ({ it, s: perfOf(it, data, use) }))
    .filter((x): x is { it: Prebuilt; s: PerfScore & { score: number } } => x.s.score != null)
    .sort((a, b) => b.s.score - a.s.score || a.it.price - b.it.price)
  if (!xs.length) return new Map()
  const top = xs[0].s.score
  // 빌드는 음수(분)라 1위 대비는 '시간의 역수' 비로 잰다
  const rel = (v: number) => (use === 'build' ? (top / v) * 100 : (v / top) * 100)
  return new Map(
    xs.map((x, i) => {
      const faster = xs.slice(0, i).filter((y) => y.s.score > x.s.score * (use === 'build' ? 0.95 : 1.05))
      const cheapest = [...faster].sort((a, b) => a.it.price - b.it.price)[0]
      const gain = cheapest ? (use === 'build' ? x.s.score / cheapest.s.score : cheapest.s.score / x.s.score) : 0
      return [
        x.it.key,
        {
          rank: i + 1,
          of: xs.length,
          score: x.s,
          rel: rel(x.s.score),
          next: cheapest ? { key: cheapest.it.key, name: cheapest.it.name, gainPct: (gain - 1) * 100, extra: cheapest.it.price - x.it.price } : null,
        },
      ]
    }),
  )
}
