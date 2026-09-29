import { useEffect, useState } from 'react'

// PC 부품 화면(/hardware)이 함께 쓰는 모양·등급·시뮬레이션.
//
// 데이터 (public/hardware/)
//   parts.json  — 부품·스펙·성능 지수. hw-engine 이 제조사 공식 자료로 조사해 고친다.
//   index.json  — 분류·등급 문턱·용도. **등급은 여기 문턱으로 계산한다** — 부품에 등급을 적어
//                 두면 같은 성능인데 등급이 다른 일이 생긴다. 출처가 하나여야 한다.
//   bench.json  — 게임·AI 시뮬레이션의 기준값과 계산식 설명.
//   prices.json — catch_capture/crawlers/crawl_hardware.py 가 매일 찍는 다나와 최저가 원장.
//
// 시뮬레이션은 '추정'이다. 화면은 늘 계산 근거(기준값·식)를 같이 보여 준다.

export type Category = 'gpu' | 'cpu' | 'ram' | 'ssd' | 'hdd' | 'mainboard' | 'psu' | 'cooler' | 'case'
export type Res = 'fhd' | 'qhd' | 'uhd'
export const RES_LABEL: Record<Res, string> = { fhd: 'FHD', qhd: 'QHD', uhd: '4K' }

export interface Part {
  id: string
  category: Category
  name: string
  maker: string
  released: string | null
  status: 'current' | 'legacy'
  specs: Record<string, string | number | boolean | null>
  perf: { index: number; multi?: number; basis: string; confidence: 'seed' | 'low' | 'medium' | 'high' }
  price_query?: { q: string }
  /** 'median' 이면 이 부품은 특정 상품이 아니라 급(級)이라 최저가보다 보통 가격이 맞다 */
  price_basis?: 'min' | 'median'
  sources: { title: string; url: string }[]
  checked_at: string
  /** 제조사 공식 페이지의 대표 이미지 — 원본에서 불러오고 출처를 단다(급 단위 부품엔 없다) */
  image?: { url: string; credit: string; page: string }
}

export interface TierDef {
  tier: string
  min: number
  plain: string
}

export interface CategoryDef {
  key: Category
  name: string
  why: string
  index_label: string
  index_basis: string
  tiers: TierDef[]
}

export interface UseDef {
  key: string
  name: string
  plain: string
  res: Res
  weights: { gpu: number; cpu: number }
  min_ram_gb?: number
  prefer?: 'multi' | 'vram'
}

export interface Game {
  key: string
  name: string
  preset: string
  kind: string
  gpu100: Record<Res, number>
  cpu100: number
  vram: Record<Res, number>
  confidence: string
}

export interface LlmModel {
  key: string
  name: string
  params_b: number
  quant: string
  size_gb: number
  plain: string
}

export interface Bench {
  model: string
  games: Game[]
  llm: {
    model: string
    efficiency: number
    overhead_gb: number
    stack_factor: Record<string, number>
    models: LlmModel[]
    readable_tps: number
    comfortable_tps: number
  }
  image: { name: string; model: string; anchor: { gpu: string; seconds: number }; min_vram_gb: number }
  finetune: { key: string; name: string; vram_gb: number; plain: string }[]
  dev: { name: string; model: string; anchor_minutes: number }
  /** 제조사가 공개한 측정값 — 우리 추정(games)과 게임·옵션이 달라 따로 그린다 */
  vendor?: { gpu: string; res: string; preset: string; footnote: string; by: string; games: { name: string; fps: number }[]; source: { title: string; url: string } }[]
  vendor_note?: string
}

export interface PricePoint {
  d: string
  min: number
  median: number
  n: number
}

export interface Offer {
  pcode: string
  name: string
  price: number
  url: string
}

export interface PriceRec {
  day?: string
  min?: number
  median?: number
  n?: number
  offers?: Offer[]
  history: PricePoint[]
  last_empty?: string
}

export interface HwData {
  parts: Part[]
  categories: CategoryDef[]
  uses: UseDef[]
  bench: Bench
  prices: Record<string, PriceRec>
  priceDay: string | null
}

let cache: Promise<HwData> | null = null

async function getJson<T>(path: string, fallback?: T): Promise<T> {
  const r = await fetch(path)
  if (!r.ok) {
    if (fallback !== undefined) return fallback
    throw new Error(`${path} ${r.status}`)
  }
  return r.json()
}

function load(): Promise<HwData> {
  cache ??= Promise.all([
    getJson<{ parts: Part[] }>('/hardware/parts.json'),
    getJson<{ categories: CategoryDef[]; uses: UseDef[] }>('/hardware/index.json'),
    getJson<Bench>('/hardware/bench.json'),
    // 가격 원장은 크롤러가 한 번이라도 돌아야 생긴다. 없으면 가격 없이 보여 준다.
    getJson<{ day?: string; parts: Record<string, PriceRec> }>('/hardware/prices.json', { parts: {} }),
  ]).then(([p, idx, bench, prices]) => ({
    parts: p.parts,
    categories: idx.categories,
    uses: idx.uses,
    bench,
    prices: prices.parts ?? {},
    priceDay: prices.day ?? null,
  }))
  cache.catch(() => (cache = null))
  return cache
}

export function useHardware(): { data: HwData | null; error: string | null } {
  const [data, setData] = useState<HwData | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    load().then(setData, (e) => setError(String(e)))
  }, [])
  return { data, error }
}

// ── 등급 ────────────────────────────────────────────────────────────

export function tierOf(part: Part, cats: CategoryDef[]): TierDef | null {
  const def = cats.find((c) => c.key === part.category)
  if (!def) return null
  return def.tiers.find((t) => part.perf.index >= t.min) ?? def.tiers[def.tiers.length - 1]
}

/** 부품의 오늘 가격 — 급(級) 부품은 중앙값, 상품 부품은 최저가. 모르면 null */
export function priceOf(part: Part, prices: Record<string, PriceRec>): number | null {
  const r = prices[part.id]
  if (!r || r.min == null) return null
  if (part.price_basis === 'median') return r.median ?? r.min
  // CPU 는 같은 칩이 정품·멀티팩·벌크·병행으로 팔리고 병행이 늘 가장 싸다. 병행은 국내 정식
  // A/S 가 없어서 조립 견적의 기준값으로 쓰지 않는다 — '정품' 표기가 있는 매물의 최저가를 쓴다.
  if (part.category === 'cpu') {
    const official = (r.offers ?? []).filter((o) => o.name.includes('정품') && !o.name.includes('병행'))
    if (official.length) return Math.min(...official.map((o) => o.price))
  }
  return r.min
}

export function won(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 10_000) {
    const man = n / 10_000
    return `${man >= 100 ? Math.round(man).toLocaleString() : man.toFixed(1).replace(/\.0$/, '')}만원`
  }
  return `${n.toLocaleString()}원`
}

/** 가격 흐름 — 지난 N일 중앙값 대비 오늘이 얼마나 싼가/비싼가(%) */
export function priceMove(rec: PriceRec | undefined, days = 30): { pct: number; low: number; high: number; days: number } | null {
  const h = rec?.history ?? []
  if (h.length < 2) return null
  const last = h[h.length - 1]
  const cutoff = new Date(last.d)
  cutoff.setDate(cutoff.getDate() - days)
  const win = h.filter((p) => new Date(p.d) >= cutoff)
  const mins = win.map((p) => p.min).sort((a, b) => a - b)
  const med = mins[Math.floor(mins.length / 2)]
  return { pct: ((last.min - med) / med) * 100, low: mins[0], high: mins[mins.length - 1], days: win.length }
}

// ── 게임 시뮬레이션 ──────────────────────────────────────────────────

export interface FpsEstimate {
  fps: number
  gpuFps: number
  cpuFps: number
  bound: 'gpu' | 'cpu'
  vramShort: number
}

export function estimateFps(game: Game, res: Res, gpu: Part, cpu: Part | null): FpsEstimate {
  const gpuRaw = (game.gpu100[res] * gpu.perf.index) / 100
  const vram = Number(gpu.specs.vram_gb ?? 0)
  const need = game.vram[res]
  // VRAM 이 모자라면 텍스처를 시스템 메모리로 넘기며 급격히 느려진다. 모자란 비율만큼 깎는 단순한 근사.
  const vramShort = Math.max(0, need - vram)
  const gpuFps = vramShort > 0 ? gpuRaw * Math.max(0.35, 1 - (vramShort / need) * 1.5) : gpuRaw
  const cpuFps = cpu ? (game.cpu100 * cpu.perf.index) / 100 : Infinity
  const fps = Math.min(gpuFps, cpuFps)
  return { fps: Math.round(fps), gpuFps: Math.round(gpuFps), cpuFps: Math.round(cpuFps), bound: gpuFps <= cpuFps ? 'gpu' : 'cpu', vramShort }
}

export function fpsWord(fps: number): { word: string; tone: 'good' | 'ok' | 'bad' } {
  if (fps >= 144) return { word: '고주사율 모니터까지 채운다', tone: 'good' }
  if (fps >= 90) return { word: '매우 부드럽다', tone: 'good' }
  if (fps >= 60) return { word: '부드럽다', tone: 'ok' }
  if (fps >= 40) return { word: '할 만하다 — 옵션을 조금 내리면 60', tone: 'ok' }
  return { word: '버벅인다 — 옵션·해상도를 내려야 한다', tone: 'bad' }
}

// ── AI 시뮬레이션 ────────────────────────────────────────────────────

export interface LlmEstimate {
  fits: boolean
  tps: number
  gpuShare: number
  note: string
}

/** 언어 모델 한 개를 돌렸을 때의 생성 속도(토큰/초). 식은 bench.llm.model 에 적혀 있다. */
export function estimateLlm(bench: Bench, m: LlmModel, gpu: Part, ramBwGbs: number | null): LlmEstimate {
  const vram = Number(gpu.specs.vram_gb ?? 0)
  const bw = Number(gpu.specs.bandwidth_gbs ?? 0)
  const stack = bench.llm.stack_factor[String(gpu.specs.stack)] ?? 0.8
  const eff = bench.llm.efficiency * stack
  const room = vram - bench.llm.overhead_gb
  if (m.size_gb <= room) {
    return { fits: true, tps: (bw * eff) / m.size_gb, gpuShare: 1, note: '그래픽카드 메모리에 통째로 들어간다' }
  }
  // 넘친 부분은 시스템 메모리에서 읽는다. 한 토큰의 시간 = GPU 몫 + CPU 몫(직렬).
  const onGpu = Math.max(0, room)
  const off = m.size_gb - onGpu
  const sysBw = ramBwGbs ?? 60
  const t = onGpu / (bw * eff) + off / (sysBw * bench.llm.efficiency)
  return {
    fits: false,
    tps: 1 / t,
    gpuShare: onGpu / m.size_gb,
    note: `${Math.round((off / m.size_gb) * 100)}% 가 그래픽카드에 안 들어가 시스템 메모리에서 읽는다`,
  }
}

export function tpsWord(bench: Bench, tps: number): { word: string; tone: 'good' | 'ok' | 'bad' } {
  if (tps >= bench.llm.comfortable_tps) return { word: '말하는 속도보다 빠르다', tone: 'good' }
  if (tps >= bench.llm.readable_tps) return { word: '읽는 속도로 나온다', tone: 'ok' }
  if (tps >= 2) return { word: '기다려야 한다', tone: 'bad' }
  return { word: '사실상 못 쓴다', tone: 'bad' }
}

/** 이미지 한 장(SDXL 1024²·30스텝)에 걸리는 초. FP16 이 없으면 성능 지수로 잰다. */
export function estimateImageSec(bench: Bench, gpu: Part, parts: Part[]): number | null {
  const anchor = parts.find((p) => p.id === bench.image.anchor.gpu)
  if (!anchor) return null
  if (Number(gpu.specs.vram_gb ?? 0) < bench.image.min_vram_gb) return null
  const stack = bench.llm.stack_factor[String(gpu.specs.stack)] ?? 0.8
  const f = Number(gpu.specs.fp16_tflops)
  const fa = Number(anchor.specs.fp16_tflops)
  const ratio = f && fa ? f / fa : gpu.perf.index / anchor.perf.index
  return bench.image.anchor.seconds / (ratio * stack)
}

export function estimateBuildMin(bench: Bench, cpu: Part): number {
  return bench.dev.anchor_minutes * (100 / (cpu.perf.multi ?? cpu.perf.index))
}

// ── 조립과 호환성 ────────────────────────────────────────────────────

export type Build = Partial<Record<Category, string>>

export interface Check {
  ok: boolean
  level: 'error' | 'warn' | 'ok'
  text: string
  /** 이 검사에 걸린 분류들 — 고르는 목록이 '이 부품을 넣으면 무엇이 깨지나'를 물을 때 쓴다 */
  cats: Category[]
}

const byId = (parts: Part[]) => new Map(parts.map((p) => [p.id, p]))

/** 시스템 전체 소비 전력(W) 추정 — CPU 최대 + GPU TDP + 나머지 80W */
export function systemWatts(cpu: Part | undefined, gpu: Part | undefined): number {
  return Number(cpu?.specs.max_power_w ?? 150) + Number(gpu?.specs.tdp_w ?? 0) + 80
}

/**
 * 호환성 검사. error = 꽂히지 않거나 켜지지 않는다 · warn = 되지만 조건이 붙는다 · ok = 확인했다.
 *
 * 부품 목록(parts.json)은 칩·급 단위라 제품마다 다른 값(그래픽카드 길이, 보드 규격)은 여기서
 * 확정할 수 없다 — 그런 것은 error 가 아니라 warn 으로 '무엇을 확인하라'를 말한다.
 * 고르는 목록은 후보 하나를 넣은 조합으로 이 함수를 다시 돌려 그 분류가 걸린 error 를 보여 준다.
 */
export function checkBuild(build: Build, parts: Part[]): Check[] {
  const m = byId(parts)
  const get = (c: Category) => (build[c] ? m.get(build[c]!) : undefined)
  const cpu = get('cpu'), mb = get('mainboard'), ram = get('ram'), gpu = get('gpu')
  const psu = get('psu'), cooler = get('cooler'), cs = get('case')
  const out: Check[] = []
  const push = (level: Check['level'], text: string, cats: Category[]) => out.push({ ok: level === 'ok', level, text, cats })

  // ── 꽂히나 ──
  if (cpu && mb) {
    if (cpu.specs.socket === mb.specs.socket) push('ok', `소켓 ${cpu.specs.socket} — CPU 와 보드가 맞는다`, ['cpu', 'mainboard'])
    else push('error', `소켓이 다르다 — CPU 는 ${cpu.specs.socket}, 보드는 ${mb.specs.socket}. 꽂히지 않는다`, ['cpu', 'mainboard'])
  }
  if (ram && mb) {
    if (String(mb.specs.mem).includes(String(ram.specs.type))) push('ok', `${ram.specs.type} — 보드가 받는 메모리다`, ['ram', 'mainboard'])
    else push('error', `메모리 종류가 다르다 — 보드는 ${mb.specs.mem}, 메모리는 ${ram.specs.type}. 홈 모양이 달라 꽂히지 않는다`, ['ram', 'mainboard'])
  }
  if (ram && cpu && !String(cpu.specs.mem).includes(String(ram.specs.type))) {
    push('error', `${cpu.name} 은 ${cpu.specs.mem} 만 지원한다 — ${ram.specs.type} 로는 안 켜진다`, ['ram', 'cpu'])
  }
  if (cpu && !gpu && !cpu.specs.igpu) {
    push('error', `${cpu.name} 은 내장 그래픽이 없다 — 그래픽카드 없이는 화면이 안 나온다`, ['cpu', 'gpu'])
  }

  // ── 켜지나 ──
  if (psu && (cpu || gpu)) {
    const need = systemWatts(cpu, gpu)
    const rec = Math.max(need * 1.3, Number(gpu?.specs.psu_w ?? 0))
    const w = Number(psu.specs.watt)
    const cats: Category[] = ['psu', ...(gpu ? (['gpu'] as Category[]) : []), ...(cpu ? (['cpu'] as Category[]) : [])]
    if (w >= rec) push('ok', `파워 ${w}W — 최대 ${need}W 추정, 여유 충분`, cats)
    else if (w >= need) push('warn', `파워 ${w}W — 최대 ${need}W 는 버티지만 권장 ${Math.ceil(rec / 50) * 50}W 보다 작다`, cats)
    else push('error', `파워가 모자란다 — ${w}W 인데 최대 소비가 ${need}W 다. 부하 때 꺼진다`, cats)
  }
  if (psu && gpu && Number(gpu.specs.tdp_w) >= 250 && !psu.specs.atx3) {
    push('warn', `${gpu.name} 급은 16핀(12V-2x6) 전원을 쓰는 제품이 많다 — ATX 3.x 가 아닌 파워는 동봉 어댑터로 이어야 한다`, ['psu', 'gpu'])
  }

  // ── 식히나 ──
  if (cooler && cpu) {
    const need = Number(cpu.specs.max_power_w)
    const cap = Number(cooler.specs.cpu_watt)
    if (cap >= need) push('ok', `쿨러가 CPU 최대 ${need}W 를 감당한다`, ['cooler', 'cpu'])
    else if (cap >= Number(cpu.specs.tdp_w)) push('warn', `쿨러 ${cap}W 급 — 평소엔 되지만 최대 ${need}W 부하에선 클럭이 내려간다`, ['cooler', 'cpu'])
    else push('error', `쿨러가 모자란다 — ${cap}W 급으로 CPU 기본 ${cpu.specs.tdp_w}W 도 못 식힌다`, ['cooler', 'cpu'])
  }

  // ── 들어가나 ──
  if (cooler && cs && cooler.specs.radiator_mm && Number(cooler.specs.radiator_mm) > Number(cs.specs.max_radiator_mm)) {
    push('error', `라디에이터가 안 들어간다 — ${cooler.specs.radiator_mm}mm 인데 케이스는 ${cs.specs.max_radiator_mm}mm 까지다`, ['cooler', 'case'])
  }
  if (cooler && cs && cooler.specs.height_mm && Number(cooler.specs.height_mm) > Number(cs.specs.max_cooler_mm)) {
    push('error', `쿨러가 안 들어간다 — 높이 ${cooler.specs.height_mm}mm 인데 케이스는 ${cs.specs.max_cooler_mm}mm 까지다`, ['cooler', 'case'])
  }
  if (mb && cs && cs.specs.form === 'M-ATX') {
    push('warn', `미니타워(M-ATX) 케이스다 — 보드는 ${mb.name} 중 M-ATX 규격으로 골라야 들어간다`, ['mainboard', 'case'])
  }
  if (gpu && cs && Number(gpu.specs.tdp_w) >= 300 && Number(cs.specs.max_gpu_mm) < 360) {
    push('warn', `${gpu.name} 급은 330mm 를 넘는 제품이 많다 — 케이스 한도 ${cs.specs.max_gpu_mm}mm 와 제품 길이를 맞춰 본다(부품 상세의 제품별 스펙)`, ['gpu', 'case'])
  }

  // ── 켜지긴 하지만 조건이 붙는다 ──
  if (cpu && mb && cpu.specs.socket === mb.specs.socket && cpu.released && mb.released && monthsBetween(mb.released, cpu.released) > 3) {
    push('warn', `${mb.name} 은 ${cpu.name} 보다 먼저 나온 칩셋이다 — 재고 보드는 BIOS 를 올려야 인식할 수 있다. CPU 없이 BIOS 를 올리는 기능(플래시백)이 있는 보드를 고르거나 판매처에 업데이트 여부를 묻는다`, ['cpu', 'mainboard'])
  }
  if (cpu && mb && mb.id === 'mb-a620' && Number(cpu.specs.tdp_w) >= 120) {
    push('warn', `A620 보드는 전원부가 작아 제조사마다 고전력 CPU 지원이 다르다 — 보드의 CPU 지원 목록에 ${cpu.name} 이 있는지 확인한다`, ['cpu', 'mainboard'])
  }
  return out
}

function monthsBetween(from: string, to: string): number {
  const [y1, m1] = from.split('-').map(Number)
  const [y2, m2] = to.split('-').map(Number)
  return (y2 - y1) * 12 + (m2 - m1)
}

/** 후보 하나를 이 분류에 넣으면 생기는 '안 된다'(error) — 고르는 목록에 이유로 붙인다. */
export function conflictsOf(cat: Category, id: string, build: Build, parts: Part[]): string[] {
  return checkBuild({ ...build, [cat]: id }, parts)
    .filter((c) => c.level === 'error' && c.cats.includes(cat))
    .map((c) => c.text)
}

export function buildTotal(build: Build, parts: Part[], prices: Record<string, PriceRec>): { total: number; missing: string[] } {
  const m = byId(parts)
  let total = 0
  const missing: string[] = []
  for (const [cat, id] of Object.entries(build) as [Category, string | undefined][]) {
    if (!id) continue
    const p = m.get(id)
    if (!p) continue
    const price = priceOf(p, prices)
    if (price == null) missing.push(p.name)
    else total += price * (cat === 'ram' ? 2 : 1) // 메모리는 두 장(듀얼 채널)
  }
  return { total, missing }
}

/**
 * 예산·용도로 조합을 고른다. 욕심 많은 규칙 몇 줄이다 — 최적해가 아니라 '출발점'이다.
 *  1. 용도 비중만큼 GPU·CPU 예산을 떼고, 그 안에서 지수가 가장 높은 것을 고른다.
 *  2. 보드는 CPU 소켓에 맞는 것 중 가장 싼 것, 메모리는 보드가 받는 종류에서 용도의 최소 용량.
 *  3. 파워·쿨러는 계산한 전력을 넘는 것 중 가장 싼 것. 케이스는 중간 급.
 */
export function autoBuild(
  budget: number,
  use: UseDef,
  data: HwData,
  opts: { allow?: (p: Part) => boolean; noGpu?: boolean } = {},
): Build {
  const { parts, prices } = data
  const allow = opts.allow ?? (() => true)
  const priced = (c: Category) =>
    parts
      .filter((p) => p.category === c && p.status === 'current' && allow(p))
      .map((p) => ({ p, price: priceOf(p, prices) }))
      .filter((x): x is { p: Part; price: number } => x.price != null)
  const best = (c: Category, cap: number, score: (p: Part) => number) => {
    const xs = priced(c).filter((x) => x.price <= cap)
    xs.sort((a, b) => score(b.p) - score(a.p) || a.price - b.price)
    return xs[0]?.p ?? priced(c).sort((a, b) => a.price - b.price)[0]?.p
  }
  const cheapest = (c: Category, ok: (p: Part) => boolean) =>
    priced(c)
      .filter((x) => ok(x.p))
      .sort((a, b) => a.price - b.price)[0]?.p

  const gpuScore = (p: Part) => (use.prefer === 'vram' ? Number(p.specs.vram_gb) * 10 + p.perf.index / 10 : p.perf.index)
  const cpuScore = (p: Part) => (use.prefer === 'multi' ? (p.perf.multi ?? p.perf.index) : p.perf.index)
  // 내장 그래픽을 골랐으면 그래픽카드를 비우고, CPU 는 내장 그래픽이 있는 것만 본다.
  const gpu = opts.noGpu ? undefined : best('gpu', budget * use.weights.gpu, gpuScore)
  const cpuScoreFor = (p: Part) => (opts.noGpu && !p.specs.igpu ? -1 : cpuScore(p))
  const cpu = best('cpu', budget * use.weights.cpu, cpuScoreFor)
  // 보드는 소켓이 맞는 것 중 경고(BIOS·전원부)까지 없는 가장 싼 것. 그런 게 없으면 소켓만 맞는 가장 싼 것.
  const clean = (p: Part) =>
    !!cpu && !checkBuild({ cpu: cpu.id, mainboard: p.id }, parts).some((c) => c.level !== 'ok')
  const mb = cpu
    ? (cheapest('mainboard', clean) ?? cheapest('mainboard', (p) => p.specs.socket === cpu.specs.socket))
    : undefined
  const minGb = use.min_ram_gb ?? 32
  const perStick = minGb / 2
  const ram = mb
    ? (cheapest('ram', (p) => String(mb.specs.mem).includes(String(p.specs.type)) && Number(p.specs.capacity_gb) >= perStick) ??
      cheapest('ram', (p) => String(mb.specs.mem).includes(String(p.specs.type))))
    : undefined
  const need = systemWatts(cpu, gpu)
  const psu = cheapest('psu', (p) => Number(p.specs.watt) >= Math.max(need * 1.3, Number(gpu?.specs.psu_w ?? 0)))
  const cooler = cpu ? cheapest('cooler', (p) => Number(p.specs.cpu_watt) >= Number(cpu.specs.max_power_w) * 0.9) : undefined
  const ssd = best('ssd', budget * 0.08, (p) => Number(p.specs.capacity_gb) * 10 + p.perf.index)
  const cs = cheapest('case', (p) => Number(p.specs.max_gpu_mm) >= 380 && (!cooler?.specs.radiator_mm || Number(cooler.specs.radiator_mm) <= Number(p.specs.max_radiator_mm)))
  return { gpu: gpu?.id, cpu: cpu?.id, mainboard: mb?.id, ram: ram?.id, psu: psu?.id, cooler: cooler?.id, ssd: ssd?.id, case: cs?.id }
}

export const CATEGORY_ORDER: Category[] = ['cpu', 'gpu', 'mainboard', 'ram', 'ssd', 'hdd', 'psu', 'cooler', 'case']

/** 스펙 표의 열 — 분류마다 전문가가 비교하는 값 */
export const SPEC_COLUMNS: Record<Category, { key: string; label: string; unit?: string }[]> = {
  gpu: [
    { key: 'vram_gb', label: 'VRAM', unit: 'GB' },
    { key: 'mem_type', label: '메모리' },
    { key: 'bandwidth_gbs', label: '대역폭', unit: 'GB/s' },
    { key: 'cores', label: '코어' },
    { key: 'fp16_tflops', label: 'FP16', unit: 'TF' },
    { key: 'tdp_w', label: '전력', unit: 'W' },
    { key: 'psu_w', label: '권장 파워', unit: 'W' },
    { key: 'stack', label: 'AI 스택' },
  ],
  cpu: [
    { key: 'socket', label: '소켓' },
    { key: 'cores', label: '코어' },
    { key: 'threads', label: '스레드' },
    { key: 'boost_ghz', label: '부스트', unit: 'GHz' },
    { key: 'l3_mb', label: 'L3', unit: 'MB' },
    { key: 'tdp_w', label: 'TDP', unit: 'W' },
    { key: 'max_power_w', label: '최대', unit: 'W' },
    { key: 'mem', label: '메모리' },
    { key: 'igpu', label: '내장 GPU' },
  ],
  ram: [
    { key: 'type', label: '종류' },
    { key: 'capacity_gb', label: '용량', unit: 'GB' },
    { key: 'speed_mts', label: '속도', unit: 'MT/s' },
    { key: 'cl', label: 'CL' },
    { key: 'latency_ns', label: '지연', unit: 'ns' },
    { key: 'dual_bandwidth_gbs', label: '2장 대역폭', unit: 'GB/s' },
  ],
  ssd: [
    { key: 'interface', label: '인터페이스' },
    { key: 'capacity_gb', label: '용량', unit: 'GB' },
    { key: 'seq_read_mbs', label: '읽기', unit: 'MB/s' },
    { key: 'seq_write_mbs', label: '쓰기', unit: 'MB/s' },
    { key: 'tbw', label: '수명', unit: 'TBW' },
    { key: 'dram', label: 'DRAM' },
    { key: 'nand', label: '낸드' },
  ],
  hdd: [
    { key: 'capacity_tb', label: '용량', unit: 'TB' },
    { key: 'rpm', label: '회전', unit: 'rpm' },
    { key: 'cache_mb', label: '캐시', unit: 'MB' },
    { key: 'cmr', label: 'CMR' },
    { key: 'use', label: '용도' },
  ],
  mainboard: [
    { key: 'socket', label: '소켓' },
    { key: 'mem', label: '메모리' },
    { key: 'pcie_gpu', label: '그래픽 슬롯' },
    { key: 'pcie_m2', label: 'M.2' },
    { key: 'cpu_oc', label: 'CPU 오버클럭' },
    { key: 'usb4', label: 'USB4' },
  ],
  psu: [
    { key: 'watt', label: '정격', unit: 'W' },
    { key: 'rating', label: '80PLUS' },
    { key: 'efficiency_50pct', label: '효율(50%)', unit: '%' },
    { key: 'atx3', label: 'ATX 3.x' },
    { key: 'pcie_12v2x6', label: '12V-2x6' },
  ],
  cooler: [
    { key: 'type', label: '방식' },
    { key: 'cpu_watt', label: '감당 전력', unit: 'W' },
    { key: 'height_mm', label: '높이', unit: 'mm' },
    { key: 'radiator_mm', label: '라디에이터', unit: 'mm' },
  ],
  case: [
    { key: 'form', label: '규격' },
    { key: 'max_gpu_mm', label: 'GPU 길이', unit: 'mm' },
    { key: 'max_cooler_mm', label: '쿨러 높이', unit: 'mm' },
    { key: 'max_radiator_mm', label: '라디에이터', unit: 'mm' },
  ],
}

// ── 제품(보드 파트너 모델) ──────────────────────────────────────────
//
// 부품(parts.json)은 칩 단위다 — "RTX 5090". 실제로 사는 물건은 그 칩을 얹은 제품이다 —
// "ASUS ROG Astral RTX 5090 OC". 길이·두께·팬·OC 클럭·구성품은 제품마다 다르고, 케이스에
// 들어가느냐는 이 값으로 갈린다. 파일은 부품마다 하나(public/hardware/models/<부품 id>.json),
// 상세 화면을 열 때만 받는다. 스펙은 제조사 공식 페이지에서 채운다(다나와 스펙 문자열은 쓰지 않는다).
//
// 같은 제품이라도 유통사마다 다나와 상품번호가 다르다(피씨디렉트·제이씨현…). 그래서 제품은
// 이름 규칙(match)으로 그날의 매물들을 모아 가진다 — 크롤러의 거름 규칙과 같은 방식이다.

export interface Model {
  id: string
  name: string
  brand: string
  code?: string
  match: { must: string[]; not?: string[] }
  specs: Record<string, string | number | boolean | string[] | null>
  sources: { title: string; url: string }[]
  confidence: 'low' | 'medium' | 'high'
  checked_at: string
  note?: string
  /** 제조사 공식 페이지의 대표 이미지 — 파일로 복사하지 않고 원본에서 불러온다(출처 표시) */
  image?: { url: string; credit: string; page: string }
  /** 공식 페이지가 말하는 내구성 관련 사실(팬 베어링·금속 백플레이트 등) */
  durability?: { fan_bearing?: string | null; notes?: string[] }
}

const modelCache = new Map<string, Promise<Model[]>>()

export function useModels(partId: string): Model[] | null {
  const [models, setModels] = useState<{ id: string; list: Model[] } | null>(null)
  useEffect(() => {
    let p = modelCache.get(partId)
    if (!p) {
      // 아직 조사 안 한 부품은 파일이 없다 — 빈 목록으로 본다.
      p = fetch(`/hardware/models/${partId}.json`)
        .then((r) => (r.ok ? r.json() : { models: [] }))
        .then((d: { models?: Model[] }) => d.models ?? [])
        .catch(() => [])
      modelCache.set(partId, p)
    }
    let alive = true
    p.then((list) => alive && setModels({ id: partId, list }))
    return () => {
      alive = false
    }
  }, [partId])
  return models?.id === partId ? models.list : null
}

const norm = (s: string) => s.replace(/\s+/g, '').toLowerCase()
const has = (name: string, token: string) => token.split('|').some((t) => name.includes(norm(t)))

export function offerMatches(offer: Offer, m: Model): boolean {
  const n = norm(offer.name)
  return m.match.must.every((t) => has(n, t)) && !(m.match.not ?? []).some((t) => has(n, t))
}

/** 매물 → 제품. 어느 제품에도 안 걸린 매물은 '스펙 조사 전' 으로 따로 돌려준다. */
export function groupOffers(offers: Offer[], models: Model[]): { byModel: Map<string, Offer[]>; rest: Offer[] } {
  const byModel = new Map<string, Offer[]>(models.map((m) => [m.id, []]))
  const rest: Offer[] = []
  for (const o of offers) {
    const m = models.find((x) => offerMatches(o, x))
    if (m) byModel.get(m.id)!.push(o)
    else rest.push(o)
  }
  return { byModel, rest }
}

// ── 유통·내구성 안내 (public/hardware/guide.json) ─────────────────────
//
// 같은 물건이라도 '누가 들여왔고 어떤 형태로 파나'에 따라 보증과 A/S 가 다르다.
//   CPU  — 정품 · 멀티팩 · 밸류팩 · 벌크 정품 · 벌크 병행. 병행은 국내 정식 A/S 가 없어 싸다.
//   GPU  — 상품명 끝의 유통사(대원씨티에스·제이씨현·인텍앤컴퍼니…)가 A/S 를 맡는다.
// 매물 이름에서 형태·유통사를 읽어 붙인다. 내구성 메모는 부품·분류에 걸린다.

export interface SaleForm {
  key: string
  label: string
  tokens: string[]
  excludes?: string[]
  box?: boolean | null
  cooler?: string | null
  warranty_years?: number | null
  service?: string | null
  plain: string
  official: boolean
  sources: { title: string; url: string }[]
}

export interface Distributor {
  name: string
  aliases?: string[]
  brands: string[]
  warranty_years?: number | null
  service?: string | null
  parallel_import_service?: string | null
  as_url?: string | null
  sources: { title: string; url: string }[]
}

export interface DurabilityNote {
  key: string
  applies_to: string[]
  level: '주의' | '참고'
  title: string
  plain: string
  sources: { title: string; url: string }[]
}

export interface Guide {
  forms: SaleForm[]
  distributors: Distributor[]
  durability: DurabilityNote[]
}

let guideCache: Promise<Guide> | null = null

export function useGuide(): Guide | null {
  const [g, setG] = useState<Guide | null>(null)
  useEffect(() => {
    guideCache ??= fetch('/hardware/guide.json')
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d ?? { forms: [], distributors: [], durability: [] })
      .catch(() => ({ forms: [], distributors: [], durability: [] }))
    let alive = true
    guideCache.then((x) => alive && setG(x))
    return () => {
      alive = false
    }
  }, [])
  return g
}

/** 매물 이름 → 판매 형태(CPU). 토큰이 모두 있고 제외어가 없는 첫 형태. 뒤에 적힌 형태일수록 구체적이라 긴 것부터 본다. */
export function formOf(name: string, forms: SaleForm[]): SaleForm | null {
  const n = norm(name)
  const sorted = [...forms].sort((a, b) => b.tokens.length - a.tokens.length)
  return (
    sorted.find((f) => f.tokens.every((t) => has(n, t)) && !(f.excludes ?? []).some((t) => has(n, t))) ?? null
  )
}

/** 매물 이름 → 유통사. 상품명 끝에 붙는 수입사 이름으로 찾는다. */
export function distributorOf(name: string, ds: Distributor[]): Distributor | null {
  const n = norm(name)
  return ds.find((d) => [d.name, ...(d.aliases ?? [])].some((a) => n.includes(norm(a)))) ?? null
}

export function notesFor(part: Part, notes: DurabilityNote[]): DurabilityNote[] {
  return notes.filter((x) => x.applies_to.some((a) => a === part.id || a === `category:${part.category}`))
}

/** 제품 스펙 표의 열 — 분류마다. 아직 조사 안 한 분류는 비어 있다. */
export const MODEL_COLUMNS: Partial<Record<Category, { key: string; label: string; unit?: string }[]>> = {
  gpu: [
    { key: 'boost_mhz', label: '부스트', unit: 'MHz' },
    { key: 'oc_mhz', label: 'OC', unit: 'MHz' },
    { key: 'length_mm', label: '길이', unit: 'mm' },
    { key: 'thickness_mm', label: '두께', unit: 'mm' },
    { key: 'slots', label: '슬롯' },
    { key: 'fans', label: '팬' },
    { key: 'power_connector', label: '전원' },
    { key: 'psu_w', label: '권장 파워', unit: 'W' },
    { key: 'outputs', label: '출력' },
    { key: 'dual_bios', label: '듀얼 BIOS' },
    { key: 'zero_fan', label: '0dB' },
    { key: 'backplate', label: '백플레이트' },
    { key: 'lighting', label: '조명' },
  ],
  mainboard: [
    { key: 'form', label: '규격' },
    { key: 'vrm', label: '전원부' },
    { key: 'm2_slots', label: 'M.2' },
    { key: 'dimm_slots', label: '메모리 슬롯' },
    { key: 'lan', label: '유선' },
    { key: 'wifi', label: '무선' },
    { key: 'usb_rear', label: '후면 USB' },
  ],
  cooler: [
    { key: 'height_mm', label: '높이', unit: 'mm' },
    { key: 'fans', label: '팬' },
    { key: 'tdp_w', label: '제조사 TDP', unit: 'W' },
    { key: 'noise_dba', label: '소음', unit: 'dBA' },
    { key: 'sockets', label: '소켓' },
  ],
  case: [
    { key: 'form', label: '규격' },
    { key: 'max_gpu_mm', label: 'GPU 길이', unit: 'mm' },
    { key: 'max_cooler_mm', label: '쿨러 높이', unit: 'mm' },
    { key: 'max_radiator_mm', label: '라디에이터', unit: 'mm' },
    { key: 'fans_included', label: '기본 팬' },
  ],
  psu: [
    { key: 'modular', label: '모듈러' },
    { key: 'length_mm', label: '길이', unit: 'mm' },
    { key: 'fan_mm', label: '팬', unit: 'mm' },
    { key: 'warranty_years', label: '보증', unit: '년' },
    { key: 'pcie_12v2x6', label: '12V-2x6' },
  ],
}

export function fmtSpec(v: string | number | boolean | string[] | null | undefined, unit?: string): string {
  if (v == null || v === '') return '—'
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'boolean') return v ? '있음' : '없음'
  return unit ? `${typeof v === 'number' ? v.toLocaleString() : v} ${unit}` : String(v)
}
