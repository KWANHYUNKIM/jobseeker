import { useEffect, useState } from 'react'
import { checkBuild, estimateFps, priceOf, systemWatts, tierOf, type Build, type HwData, type Part } from './hardware'

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

  // 호환성 — 판매 구성이 우리 검사에 걸리면 표기가 잘못됐거나 정말 문제가 있는 것이다
  const build: Build = { cpu: cpu?.id, gpu: gpu?.id, mainboard: mb?.id, ram: ram?.id, psu: psu?.id }
  const errors = checkBuild(build, data.parts).filter((x) => x.level === 'error').map((x) => x.text)

  const games = data.bench.games
  // CPU 를 모르면 CPU 천장을 못 재서 fps 가 부풀려진다 — 계산하지 않는다(순위에서도 빠진다).
  const qhdFps = gpu && cpu ? Math.round(games.reduce((s, g) => s + estimateFps(g, 'qhd', gpu, cpu).fps, 0) / games.length) : null

  const good: string[] = []
  const bad: string[] = []
  if (premiumPct != null) {
    if (premiumPct <= 5) good.push(`부품값 합계와 거의 같다(+${Math.round(premiumPct)}%) — 조립·검수값을 거의 안 받는 셈이다`)
    else if (premiumPct <= 15) good.push(`조립 프리미엄 +${Math.round(premiumPct)}% — 조립·검수·A/S 값으로 흔한 범위다`)
    else if (premiumPct >= 25) bad.push(`부품을 따로 사면 약 ${Math.round(premium! / 10000)}만원(${Math.round(premiumPct)}%) 싸다`)
    else bad.push(`조립 프리미엄 +${Math.round(premiumPct)}% — 조금 비싸다`)
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

  return { lines, sum, premium, premiumPct, unknown, cpu, gpu, qhdFps, good, bad, errors }
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
