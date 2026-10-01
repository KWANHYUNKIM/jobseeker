import { useEffect, useState } from 'react'
import { fetchPrices } from '../api'

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
  /** 그래픽 메모리 최소(GB) — 넘는 카드가 있으면 그 아래는 조합 후보에서 뺀다 */
  min_vram_gb?: number
  /** 그래픽카드를 무엇으로 재나 — 'video' 면 bench.video 의 실측 효과 점수 */
  gpu_score?: 'video'
  /** 그래픽카드 없이 내장 그래픽으로 짠다(사무용) */
  no_gpu?: boolean
  /** 이 용도를 누르면 예산을 여기로 옮긴다 — 조합은 예산을 채우므로 용도에 맞는 출발 금액이 필요하다 */
  budget?: number
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
  dev: { name: string; model: string; anchor_minutes: number; serial_fraction?: number }
  /** 영상 편집 — 추정식이 아니라 PugetBench for DaVinci Resolve 실측(사용자 제출) 점수 */
  video?: {
    name: string
    model: string
    /** 효과 점수의 기준(RTX 5090) — 막대 길이를 여기에 맞춘다 */
    effects_top: number
    vram_min_gb: Record<'fhd' | 'uhd' | '8k', number>
    ram_min_gb: Record<'fhd' | 'uhd' | '6k' | '8k', number>
    gpu: Record<string, VideoScore>
    gpu_note?: string
    sources: { title: string; url: string }[]
  }
  /** 제조사가 공개한 측정값 — 우리 추정(games)과 게임·옵션이 달라 따로 그린다 */
  vendor?: { gpu: string; res: string; preset: string; footnote: string; by: string; games: { name: string; fps: number }[]; source: { title: string; url: string } }[]
  vendor_note?: string
}

export interface VideoScore {
  overall: number
  /** 색보정·노이즈 제거 같은 GPU 효과 — 그래픽카드를 가장 잘 가른다 */
  effects: number
  /** 카메라·폰 원본(H.264·HEVC) 재생 */
  longgop: number
  raw: number
  /** NVIDIA 하드웨어 인코더 수 — AMD 는 null */
  nvenc: number | null
  /** 10비트 4:2:2 를 하드웨어로 푸는 코덱 */
  dec422: ('h264' | 'hevc')[]
  av1_enc: boolean
  src: string
  note?: string
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
  /** 다나와 통합검색(기본 정렬 = 인기상품순)에서 몇 번째였나. 순위가 생기기 전 원장에는 없다 */
  rank?: number
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
  // 없는 파일도 404 가 아니라 200 으로 올 수 있다 — SPA 폴백이 index.html 을 돌려준다
  // (vite 개발 서버도, 운영 nginx 도). 그걸 JSON 으로 읽다 터지면 대체값이 있는
  // 파일(가격 원장처럼 크롤러가 한 번 돌아야 생기는 것) 하나 때문에 탭 전체가 죽는다.
  if (fallback !== undefined && !(r.headers.get('content-type') ?? '').includes('json')) return fallback
  return r.json()
}

function load(): Promise<HwData> {
  cache ??= Promise.all([
    getJson<{ parts: Part[] }>('/hardware/parts.json'),
    getJson<{ categories: CategoryDef[]; uses: UseDef[] }>('/hardware/index.json'),
    getJson<Bench>('/hardware/bench.json'),
    // 가격 원장은 크롤러가 한 번이라도 돌아야 생긴다. 없으면 가격 없이 보여 준다.
    fetchPrices(),
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

/**
 * 빌드 시간 — 암달의 법칙. 9950X(멀티 100)의 시간을 기준으로, 병렬로 줄지 않는 몫(serial_fraction)과
 * 멀티 지수에 반비례해 줄어드는 몫을 더한다. serial_fraction 이 없으면 0(순수 비례 — 예전 식).
 */
export function estimateBuildMin(bench: Bench, cpu: Part): number {
  const s = Math.min(Math.max(bench.dev.serial_fraction ?? 0, 0), 1)
  const multi = cpu.perf.multi ?? cpu.perf.index
  return bench.dev.anchor_minutes * (s + (1 - s) * (100 / multi))
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

  // ── 열을 빼나 ── 케이스는 급 단위라 팬 배치를 모른다 — 이 발열에 필요한 팬 수를 말하고 제품은 상세에서 고른다
  if (cs && (cpu || gpu)) {
    const heat = caseHeat(cpu, gpu)
    const need = fansNeeded(heat)
    const text = `CPU+그래픽카드 발열 최대 ${heat}W — 흡기 ${need.intake}·배기 ${need.exhaust} 이상${need.mesh ? ', 앞면 메시' : ''}인 케이스로 고른다(부품 상세의 제품별 팬 배치)`
    push(need.mesh ? 'warn' : 'ok', text, ['case', ...(gpu ? (['gpu'] as Category[]) : []), ...(cpu ? (['cpu'] as Category[]) : [])])
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

// ── 케이스 — 크기와 바람길 ──────────────────────────────────────────
//
// 케이스는 부품을 담는 통이면서 열을 빼는 길이다. CPU·그래픽카드가 낸 열은 결국 케이스 팬이
// 밖으로 내보낸다 — 앞·옆·아래로 찬 공기를 들이고(흡기) 뒤·위로 더운 공기를 뺀다(배기).
// 제품마다 기본으로 들어 있는 팬(fans_included)과 더 달 수 있는 자리(fan_mounts), 공기가 들어오는
// 면(intake_panel: 메시·틈새·막힘)은 models/case-*.json 에 제조사 공식 사양으로 적혀 있다.
//
// 몇 W 에 팬 몇 개가 필요한가는 측정값이 아니라 **우리 경험 규칙**이다(fansNeeded). 화면도 그렇게 적는다.

export type FanPos = 'front' | 'side' | 'bottom' | 'top' | 'rear'
export interface CaseFan {
  pos: FanPos
  mm: number | string
  n: number
}

export const FAN_POS: Record<FanPos, string> = { front: '앞', side: '옆', bottom: '아래', top: '위', rear: '뒤' }
const INTAKE_POS: FanPos[] = ['front', 'side', 'bottom']

/** 케이스가 빼야 하는 열(W) — CPU 최대 전력 + 그래픽카드 TDP. 보드·메모리·SSD 몫은 작아서 뺀다 */
export function caseHeat(cpu: Part | undefined, gpu: Part | undefined): number {
  return Number(cpu?.specs.max_power_w ?? 0) + Number(gpu?.specs.tdp_w ?? 0)
}

/** 경험 규칙 — 이 발열이면 흡기·배기 팬이 몇 개 있어야 하나, 앞면이 메시여야 하나 */
export function fansNeeded(heat: number): { intake: number; exhaust: number; mesh: boolean } {
  if (heat < 250) return { intake: 1, exhaust: 1, mesh: false }
  if (heat < 450) return { intake: 2, exhaust: 1, mesh: false }
  return { intake: 3, exhaust: 1, mesh: true }
}

export function caseFans(specs: Model['specs']) {
  const list = (k: string) => (Array.isArray(specs[k]) ? (specs[k] as unknown as CaseFan[]) : null)
  const inc = list('fans_included')
  const mounts = list('fan_mounts')
  const sum = (xs: CaseFan[] | null, pos?: FanPos[]) =>
    xs == null ? null : xs.filter((f) => !pos || pos.includes(f.pos)).reduce((a, f) => a + Number(f.n || 0), 0)
  return {
    included: inc,
    mounts,
    intake: sum(inc, INTAKE_POS),
    exhaust: sum(inc, ['top', 'rear']),
    total: sum(inc),
    slots: sum(mounts),
  }
}

/** '앞 120×3 · 뒤 120×1' — 기본 팬 배치를 한 줄로 */
export function fanLayout(fans: CaseFan[] | null): string {
  if (fans == null) return '—'
  if (!fans.length) return '없음'
  return fans.map((f) => `${FAN_POS[f.pos] ?? f.pos} ${f.mm}×${f.n}`).join(' · ')
}

/** 바깥 크기 '가로×깊이×높이' 와 부피(L) */
export function caseSize(specs: Model['specs']): { text: string; liters: number | null } {
  const w = Number(specs.width_mm), d = Number(specs.depth_mm), h = Number(specs.height_mm)
  if (!w || !d || !h) return { text: '—', liters: null }
  return { text: `${w}×${d}×${h}`, liters: Math.round((w * d * h) / 1e5) / 10 }
}

export interface AirflowVerdict {
  level: 'ok' | 'warn' | 'bad'
  lines: string[]
}

/** 이 케이스(기본 구성 그대로)가 이 발열을 빼나 — 부족하면 무엇을 더하면 되나 */
export function airflowFor(specs: Model['specs'], heat: number): AirflowVerdict {
  const f = caseFans(specs)
  const need = fansNeeded(heat)
  const panel = specs.intake_panel as string | null
  const lines: string[] = []
  let level: AirflowVerdict['level'] = 'ok'
  const worse = (l: AirflowVerdict['level']) => {
    if (l === 'bad' || (l === 'warn' && level === 'ok')) level = l
  }
  if (f.included == null) return { level: 'warn', lines: ['기본 팬 구성을 아직 확인하지 못했다.'] }
  const addIn = Math.max(0, need.intake - (f.intake ?? 0))
  const addOut = Math.max(0, need.exhaust - (f.exhaust ?? 0))
  if (!f.total) {
    worse(heat >= 250 ? 'bad' : 'warn')
    lines.push('기본 팬이 없다 — 케이스 팬을 따로 사서 달아야 한다.')
  }
  if (addIn || addOut) {
    worse(f.total ? 'warn' : level)
    const more = [addIn ? `흡기 ${addIn}개` : '', addOut ? `배기 ${addOut}개` : ''].filter(Boolean).join(' · ')
    const room = f.slots != null && f.total != null ? ` (팬 자리 ${f.slots}곳 중 ${f.total}곳이 차 있다)` : ''
    lines.push(`${heat}W 를 빼려면 ${more} 를 더 단다${room}.`)
  } else {
    lines.push(`기본 팬(흡기 ${f.intake} · 배기 ${f.exhaust})으로 ${heat}W 를 뺀다.`)
  }
  if ((f.exhaust ?? 0) > (f.intake ?? 0) && (f.intake ?? 0) > 0) {
    lines.push('배기가 흡기보다 많다(음압) — 필터 없는 틈으로 먼지가 든다. 위 팬 하나를 흡기로 돌려 달면 균형이 맞는다.')
  }
  if (panel === '막힘') {
    worse(heat >= 300 ? 'bad' : 'warn')
    lines.push('공기가 들어오는 면이 막혀 있다 — 팬을 늘려도 들어올 길이 좁아 소음이 커진다.')
  } else if (panel === '틈새' && need.mesh) {
    worse('warn')
    lines.push('앞면이 유리·판이고 틈으로 공기를 들인다 — 이 발열이면 메시 앞면이 더 식는다.')
  }
  return { level, lines }
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
 * 예산·용도로 조합을 고른다 — **예산을 채운다**. 고른 금액이 1000만원이면 1000만원어치를 짠다.
 * 비싼 기계는 돈으로 시간을 사는 일이라, 남는 돈을 두고 싼 부품에 멈추지 않는다.
 *
 *  1. 그래픽카드 × CPU 쌍을 모두 본다. 각 쌍에 보드·메모리·SSD 후보를 붙이고, 파워·쿨러·케이스는
 *     '켜지고 식는' 가장 싼 것으로 두어 예산 안에 드는 조합만 남긴다.
 *  2. 그중 쓸모(utility)가 가장 큰 것 — 게임 용도는 예상 평균 fps(CPU 가 천장인 것까지 센다),
 *     나머지는 용도 비중으로 섞은 GPU·CPU 지수. 여기에 메모리·SSD·보드를 조금 더한다.
 *  3. 남은 돈으로 쿨러(최대 전력까지)·파워(여유 50%)·케이스를 올린다.
 * 예산 안에 드는 조합이 없으면 가장 싼 조합을 낸다(화면이 '예산보다 얼마 많다'를 말한다).
 *
 * 부품 목록은 급이 띄엄띄엄이라(RTX 5080 다음이 5090) 예산을 다 못 쓰는 구간이 있다. 예산의 90% 도
 * 못 쓰게 되면 예산의 110% 까지('1000만원대') 넓혀 한 급 위를 넣고, 그랬다는 것을 stretched 로 알린다.
 * 그래도 남으면 억지로 쓰지 않고 **한 단계 위**(성능이 3% 넘게 오르는 가장 싼 조합)의 값과 오르는 폭을 낸다.
 */
export interface BuildPlan {
  build: Build
  cost: number
  /** 예산 안에서는 이 값까지밖에 못 써서 110% 까지 넓혔다 — 넓히지 않았으면 null */
  stretched: { within: number } | null
  /** 예산을 넘지만 더 빠른 가장 싼 조합 — 없으면 null */
  next: { cost: number; gainPct: number; gpu: string | null; cpu: string } | null
}

export function autoBuild(budget: number, use: UseDef, data: HwData, opts: { allow?: (p: Part) => boolean; noGpu?: boolean } = {}): Build {
  return planBuild(budget, use, data, opts).build
}

export function planBuild(
  budget: number,
  use: UseDef,
  data: HwData,
  opts: { allow?: (p: Part) => boolean; noGpu?: boolean } = {},
): BuildPlan {
  const { parts, prices, bench } = data
  const allow = opts.allow ?? (() => true)
  type P = { p: Part; price: number }
  const priced = (c: Category): P[] =>
    parts
      .filter((p) => p.category === c && p.status === 'current' && allow(p))
      .map((p) => ({ p, price: priceOf(p, prices) }))
      .filter((x): x is P => x.price != null)
      .sort((a, b) => a.price - b.price)
  const max = (xs: number[]) => Math.max(1e-9, ...xs)
  const noGpu = opts.noGpu || !!use.no_gpu

  // 용도의 그래픽 메모리 최소선(영상 4K = 12GB) — 넘는 카드가 있으면 그 아래는 후보에서 뺀다
  const gpuAll = priced('gpu')
  const gpuFit = use.min_vram_gb ? gpuAll.filter((x) => Number(x.p.specs.vram_gb) >= use.min_vram_gb!) : gpuAll
  const gpus: (P | null)[] = noGpu ? [null] : gpuFit.length ? gpuFit : gpuAll
  // 내장 그래픽으로 짜면 내장 그래픽이 있는 CPU 만 — 없는 CPU 는 화면이 안 나온다
  const cpuAll = priced('cpu')
  const cpus = noGpu ? cpuAll.filter((x) => x.p.specs.igpu) : cpuAll
  const boards = priced('mainboard'), rams = priced('ram'), ssds = priced('ssd')
  const psus = priced('psu'), coolers = priced('cooler'), cases = priced('case')
  if (!cpus.length) return { build: {}, cost: 0, stretched: null, next: null }

  // ── 쓸모 ──
  // 영상 편집은 게임 지수가 아니라 Puget 실측 효과 점수로 잰다 — 실측 없는 카드(전부 8GB 이하)는 맨 뒤
  const video = use.gpu_score === 'video' ? bench.video : undefined
  const gpuScore = (p: Part) =>
    use.prefer === 'vram'
      ? Number(p.specs.vram_gb) * 10 + p.perf.index / 10
      : video
        ? (video.gpu[p.id]?.effects ?? 0)
        : p.perf.index
  const cpuScore = (p: Part) => (use.prefer === 'multi' ? (p.perf.multi ?? p.perf.index) : p.perf.index)
  const gMax = max(gpus.map((g) => (g ? gpuScore(g.p) : 0)))
  const cMax = max(cpus.map((c) => cpuScore(c.p)))
  const game = use.key.startsWith('game') && !noGpu
  const fps = (g: Part, c: Part) => bench.games.reduce((s, x) => s + estimateFps(x, use.res, g, c).fps, 0) / max([bench.games.length])
  const fpsMax = game ? max(gpus.flatMap((g) => (g ? cpus.map((c) => fps(g.p, c.p)) : []))) : 1
  const wg = noGpu ? 0 : use.weights.gpu, wc = use.weights.cpu
  // 영상: 카메라 원본(10비트 4:2:2)을 그래픽카드(RTX 50)도 인텔 내장 그래픽도 못 풀면 CPU 가 풀어
  // 타임라인이 끊긴다 — 그런 조합은 15% 깎는다(깎는 폭은 우리 가중치)
  const decodes422 = (g: Part | null, c: Part) =>
    !!(g && video?.gpu[g.id]?.dec422.length) || (c.maker === 'Intel' && !!c.specs.igpu)
  const core = (g: Part | null, c: Part) =>
    game && g
      ? fps(g, c) / fpsMax
      : ((wg * (g ? gpuScore(g) / gMax : 0) + wc * (cpuScore(c) / cMax)) / (wg + wc)) * (video && !decodes422(g, c) ? 0.85 : 1)
  const ramMax = max(rams.map((r) => Number(r.p.specs.capacity_gb)))
  const ssdCap = max(ssds.map((s) => Number(s.p.specs.capacity_gb)))
  const ssdIdx = max(ssds.map((s) => s.p.perf.index))
  const mbIdx = max(boards.map((b) => b.p.perf.index))
  const ramIdx = max(rams.map((r) => r.p.perf.index))
  // 메모리를 많이 쓰는 용도(개발·AI·영상)는 메모리·저장장치에 더 쓴다
  const heavy = (use.min_ram_gb ?? 32) >= 32
  const side = heavy ? 0.25 : 0.15
  const extra = (mb: P, ram: P, ssd: P) =>
    (heavy ? 0.5 : 0.35) * (0.8 * (Number(ram.p.specs.capacity_gb) / ramMax) + 0.2 * (ram.p.perf.index / ramIdx)) +
    0.35 * (0.6 * (Number(ssd.p.specs.capacity_gb) / ssdCap) + 0.4 * (ssd.p.perf.index / ssdIdx)) +
    (heavy ? 0.15 : 0.3) * (mb.p.perf.index / mbIdx)

  // ── 켜지고 식고 들어가는 가장 싼 것 ──
  const psuNeed = (g: Part | null, c: Part) => Math.max(systemWatts(c, g ?? undefined) * 1.3, Number(g?.specs.psu_w ?? 0))
  const coolerFor = (c: Part, full = false) =>
    coolers.find((x) => Number(x.p.specs.cpu_watt) >= Number(c.specs.max_power_w) * (full ? 1 : 0.9))
  const caseFor = (cooler: P | undefined, big = false) =>
    cases.find(
      (x) =>
        Number(x.p.specs.max_gpu_mm) >= (big ? 400 : 380) &&
        (!cooler?.p.specs.radiator_mm || Number(cooler.p.specs.radiator_mm) <= Number(x.p.specs.max_radiator_mm)),
    )
  // 보드: 경고(BIOS·전원부)까지 없는 것만, 그런 게 없으면 소켓만 맞는 것
  const boardsFor = new Map(
    cpus.map((c) => {
      const sock = boards.filter((b) => b.p.specs.socket === c.p.specs.socket)
      const clean = sock.filter((b) => !checkBuild({ cpu: c.p.id, mainboard: b.p.id }, parts).some((x) => x.level !== 'ok'))
      return [c.p.id, { list: clean.length ? clean : sock, clean: clean.length > 0 }]
    }),
  )
  const perStick = (use.min_ram_gb ?? 32) / 2
  const ramsFor = (mb: P, c: Part) => {
    const fit = rams.filter((r) => String(mb.p.specs.mem).includes(String(r.p.specs.type)) && String(c.specs.mem).includes(String(r.p.specs.type)))
    const enough = fit.filter((r) => Number(r.p.specs.capacity_gb) >= perStick)
    return enough.length ? enough : fit
  }

  type Pick = { g: P | null; c: P; mb: P; ram: P; ssd: P; psu: P; cooler: P; cs: P; cost: number; u: number }
  let best: Pick | null = null
  let loose: Pick | null = null
  let cheapest: Pick | null = null
  const better = (x: Pick, y: Pick | null) => !y || x.u > y.u + 1e-9 || (Math.abs(x.u - y.u) <= 1e-9 && x.cost < y.cost)
  // 쌍마다 가장 싸게 짠 값과 그 성능 — '한 단계 위'를 찾는 데 쓴다
  const pairs: { g: P | null; c: P; cost: number; core: number }[] = []
  for (const g of gpus) {
    for (const c of cpus) {
      const need = psuNeed(g?.p ?? null, c.p)
      const psu = psus.find((x) => Number(x.p.specs.watt) >= need) ?? psus[psus.length - 1]
      const cooler = coolerFor(c.p) ?? coolers[coolers.length - 1]
      const cs = caseFor(cooler) ?? cases[cases.length - 1]
      if (!psu || !cooler || !cs) continue
      const coreU = core(g?.p ?? null, c.p)
      const fixed = (g?.price ?? 0) + c.price + psu.price + cooler.price + cs.price
      const bf = boardsFor.get(c.p.id) ?? { list: [], clean: false }
      let pairMin = Infinity
      for (const mb of bf.list) {
        for (const ram of ramsFor(mb, c.p)) {
          for (const ssd of ssds) {
            const cost = fixed + mb.price + ram.price * 2 + ssd.price
            // BIOS·전원부 경고가 붙는 보드밖에 없는 CPU 는 조금 뒤로 민다(되기는 한다)
            const u = (1 - side) * coreU + side * extra(mb, ram, ssd) - (bf.clean ? 0 : 0.01)
            pairMin = Math.min(pairMin, cost)
            const pick = { g, c, mb, ram, ssd, psu, cooler, cs, cost, u }
            if (!cheapest || cost < cheapest.cost) cheapest = pick
            if (cost <= budget && better(pick, best)) best = pick
            if (cost <= budget * 1.1 && better(pick, loose)) loose = pick
          }
        }
      }
      if (pairMin < Infinity) pairs.push({ g, c, cost: pairMin, core: coreU })
    }
  }
  const stretch = !!best && !!loose && best.cost < budget * 0.9 && loose.u > best.u + 1e-9
  const stretched = stretch ? { within: best!.cost } : null
  if (stretch) best = loose
  const pick = best ?? cheapest
  if (!pick) return { build: {}, cost: 0, stretched: null, next: null }
  const pickCore = core(pick.g?.p ?? null, pick.c.p)
  const up = pairs.filter((x) => x.cost > budget && x.core > pickCore * 1.03).sort((a, b) => a.cost - b.cost)[0]
  const next = best && up ? { cost: up.cost, gainPct: (up.core / pickCore - 1) * 100, gpu: up.g?.p.name ?? null, cpu: up.c.p.name } : null

  // ── 남은 돈으로 올린다 — 안정성(쿨러·파워)이 먼저, 그다음 케이스 ──
  let left = Math.max(0, budget - pick.cost)
  const upgrade = (cur: P, next: P | undefined, set: (x: P) => void) => {
    if (next && next.price > cur.price && next.price - cur.price <= left) {
      left -= next.price - cur.price
      set(next)
    }
  }
  upgrade(pick.cooler, coolerFor(pick.c.p, true), (x) => (pick.cooler = x))
  const g = pick.g?.p
  upgrade(
    pick.psu,
    psus.find(
      (x) =>
        Number(x.p.specs.watt) >= Math.max(systemWatts(pick.c.p, g) * 1.5, Number(g?.specs.psu_w ?? 0)) &&
        (!g || Number(g.specs.tdp_w) < 250 || !!x.p.specs.atx3),
    ),
    (x) => (pick.psu = x),
  )
  if (g && Number(g.specs.tdp_w) >= 300) upgrade(pick.cs, caseFor(pick.cooler, true), (x) => (pick.cs = x))
  // 쿨러를 수랭으로 올렸으면 케이스가 라디에이터를 받는지 다시 본다
  const csOk = caseFor(pick.cooler)
  if (csOk && pick.cooler.p.specs.radiator_mm && Number(pick.cooler.p.specs.radiator_mm) > Number(pick.cs.p.specs.max_radiator_mm)) pick.cs = csOk

  const build: Build = {
    gpu: pick.g?.p.id,
    cpu: pick.c.p.id,
    mainboard: pick.mb.p.id,
    ram: pick.ram.p.id,
    ssd: pick.ssd.p.id,
    psu: pick.psu.p.id,
    cooler: pick.cooler.p.id,
    case: pick.cs.p.id,
  }
  const cost = buildTotal(build, parts, prices).total
  return { build, cost, stretched, next: next && next.cost > cost ? next : null }
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

/** 이름 읽는 법 — Ti·SUPER·XT·X3D·F·K 같은 칩 접미사와 OC·2X·LP 같은 제품 이름 */
export interface NameNote {
  key: string
  /** gpu·cpu = 칩 이름, product = 같은 칩을 얹은 제품 이름 */
  applies: 'gpu' | 'cpu' | 'product'
  maker: string | null
  token: string
  /** 이름에서 이 말을 찾는 정규식(대소문자 무시) */
  match: string
  title: string
  plain: string
  /** 차이를 숫자로 보여 줄 부품 — [이 말이 붙은 것, 안 붙은 것] */
  compare?: string[]
  sources: { title: string; url: string }[]
}

export interface Guide {
  forms: SaleForm[]
  distributors: Distributor[]
  durability: DurabilityNote[]
  names?: NameNote[]
}

export function namesIn(name: string, notes: NameNote[], applies: NameNote['applies'][]): NameNote[] {
  return notes.filter((n) => applies.includes(n.applies) && new RegExp(n.match, 'i').test(name))
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
export interface ModelColumn {
  key: string
  label: string
  unit?: string
  /** 스펙 값 하나로 안 되는 열(크기·팬 배치) — 스펙 전체를 받아 글자로 */
  fmt?: (specs: Model['specs']) => string
}

export const MODEL_COLUMNS: Partial<Record<Category, ModelColumn[]>> = {
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
    { key: 'size', label: '크기(가로×깊이×높이)', fmt: (s) => caseSize(s).text },
    { key: 'liters', label: '부피', fmt: (s) => (caseSize(s).liters == null ? '—' : `${caseSize(s).liters} L`) },
    { key: 'max_gpu_mm', label: 'GPU 길이', unit: 'mm' },
    { key: 'max_cooler_mm', label: '쿨러 높이', unit: 'mm' },
    { key: 'max_radiator_mm', label: '라디에이터', unit: 'mm' },
    { key: 'fans_included', label: '기본 팬', fmt: (s) => fanLayout(caseFans(s).included) },
    { key: 'slots', label: '팬 자리', fmt: (s) => (caseFans(s).slots == null ? '—' : `${caseFans(s).slots}곳`) },
    { key: 'intake_panel', label: '흡기면' },
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

// ── 같은 칩의 여러 제품 — 무엇이 가장 많이 팔리나 ─────────────────────
//
// "RTX 5060" 은 칩 이름이고 실제로 사는 물건은 수십 가지다(MSI 벤투스·GALAX·ZOTAC…).
// 크롤러가 다나와 통합검색의 기본 정렬(인기상품순) 순서를 매물마다 rank 로 남긴다 —
// 판매량 숫자는 공개되지 않으니 이 순서가 '많이 쓰는 제품'의 근거다.
//
// 성능: 같은 칩이면 성능은 거의 같다. 그래픽카드는 제품마다 부스트 클럭만 조금 다르니
// 칩 지수 × (제품 클럭 ÷ 기준 클럭)으로 잰다. 게임 성능은 클럭만큼 늘지 않으니 이 값은 상한이다.

export interface Variant {
  key: string
  /** 화면에 쓸 이름 — 조사한 제품이면 제품 이름, 아니면 매물 이름 */
  name: string
  model: Model | null
  offers: Offer[]
  /** 이 칩 제품 중 인기 순위(1부터). 원장에 순위가 없으면 null */
  pop: number | null
  price: number
  /** 제품의 성능 지수 — 그래픽카드는 클럭 비례 추정(조사한 제품만), CPU 는 칩 지수 그대로 */
  index: number | null
  clockPct: number | null
  form: SaleForm | null
  distributor: Distributor | null
}

const bestRank = (os: Offer[]) => Math.min(...os.map((o) => o.rank ?? Infinity))

export function variantsOf(part: Part, rec: PriceRec | undefined, models: Model[], guide: Guide | null): Variant[] {
  const offers = rec?.offers ?? []
  const ref = Number(part.specs.boost_ghz ?? 0) * 1000
  const groups: { key: string; name: string; model: Model | null; offers: Offer[] }[] = []
  if (part.category !== 'cpu' && models.length) {
    const { byModel, rest } = groupOffers(offers, models)
    for (const m of models) {
      const os = byModel.get(m.id) ?? []
      if (os.length) groups.push({ key: m.id, name: m.name, model: m, offers: os })
    }
    for (const o of rest) groups.push({ key: o.pcode, name: o.name, model: null, offers: [o] })
  } else {
    for (const o of offers) groups.push({ key: o.pcode, name: o.name, model: null, offers: [o] })
  }
  const hasRank = offers.some((o) => o.rank != null)
  const ordered = [...groups].sort((a, b) =>
    hasRank ? bestRank(a.offers) - bestRank(b.offers) : Math.min(...a.offers.map((o) => o.price)) - Math.min(...b.offers.map((o) => o.price)),
  )
  // 다나와는 용량·판매 형태만 다른 옵션(정품·멀티팩·병행)을 한 줄에 묶는다 — 같은 줄이면 같은 순위다
  const ranks = [...new Set(ordered.map((g) => bestRank(g.offers)))]
  return ordered.map((g) => {
    const boost = Number(g.model?.specs.boost_mhz ?? 0)
    const ratio = part.category === 'gpu' && boost && ref ? boost / ref : null
    const cheapest = [...g.offers].sort((a, b) => a.price - b.price)[0]
    return {
      key: g.key,
      name: g.name,
      model: g.model,
      offers: g.offers,
      pop: hasRank ? ranks.indexOf(bestRank(g.offers)) + 1 : null,
      price: cheapest.price,
      index: ratio ? Math.round(part.perf.index * ratio * 10) / 10 : part.category === 'cpu' ? part.perf.index : null,
      clockPct: ratio ? (ratio - 1) * 100 : null,
      form: part.category === 'cpu' && guide ? formOf(cheapest.name, guide.forms) : null,
      distributor: guide ? distributorOf(cheapest.name, guide.distributors) : null,
    }
  })
}

/** 대표 제품 — 인기 순위가 가장 높은 것. CPU 는 병행(국내 정식 A/S 없음)을 대표로 두지 않는다. */
export function pickOf(vs: Variant[]): Variant | null {
  const ok = vs.filter((v) => !v.form || v.form.official)
  return (ok.length ? ok : vs)[0] ?? null
}

const shortName = (p: Part) => p.name.replace('GeForce ', '').replace('Radeon ', '')

/** 왜 이 제품이 많이 팔리나 — 데이터에서 말할 수 있는 것만 문장으로 */
export function whyPopular(v: Variant, vs: Variant[], part: Part, data: HwData): string[] {
  const out: string[] = []
  if (v.pop != null) {
    out.push(`다나와 인기상품순에서 ${shortName(part)} 제품 ${vs.length}종 중 ${v.pop}위다. 인기순은 다나와가 판매·조회로 매긴 순서다 — 판매량 숫자는 공개되지 않는다.`)
  } else {
    out.push('아직 인기 순위를 받기 전의 가격 원장이라 가장 싼 제품을 대표로 두었다.')
  }
  const unit = part.category === 'gpu' || part.category === 'cpu' ? '이 칩 제품' : '이 급 제품'
  const prices = vs.map((x) => x.price).sort((a, b) => a - b)
  if (prices.length > 2) {
    const at = prices.indexOf(v.price) + 1
    out.push(
      at === 1
        ? `${unit} ${prices.length}종 가운데 가장 싸다.`
        : v.price <= prices[Math.floor(prices.length / 2)]
        ? `값이 싼 편이다 — ${prices.length}종 중 ${at}번째로 싸고, 가장 싼 것과 ${won(v.price - prices[0])} 차이다.`
        : `가장 싼 제품보다 ${won(v.price - prices[0])} 비싸다 — 값보다 브랜드·A/S·만듦새를 보고 고르는 사람이 많다는 뜻이다.`,
    )
  }
  const s = v.model?.specs
  if (s && part.category === 'case') {
    const size = caseSize(s)
    const f = caseFans(s)
    if (size.liters != null) out.push(`크기 ${size.text}mm · ${size.liters}L — 그래픽카드 ${s.max_gpu_mm ?? '?'}mm · CPU 쿨러 ${s.max_cooler_mm ?? '?'}mm 까지 들어간다.`)
    if (f.total) out.push(`기본 팬 ${f.total}개(${fanLayout(f.included)})가 들어 있다 — 팬을 따로 안 사도 흡기 ${f.intake} · 배기 ${f.exhaust} 로 바람길이 선다.`)
    else if (f.total === 0) out.push('기본 팬이 없다 — 값이 싼 대신 케이스 팬을 따로 사야 한다.')
    if (s.intake_panel === '메시') out.push('공기가 들어오는 면이 메시라 흡기가 막히지 않는다.')
  } else if (s) {
    if (Number(s.fans) === 2 && s.length_mm) out.push(`팬 2개 · 길이 ${s.length_mm}mm 로 짧다 — 작은 케이스에도 들어간다.`)
    else if (s.length_mm) out.push(`길이 ${s.length_mm}mm · 팬 ${s.fans ?? '?'}개.`)
    if (s.zero_fan) out.push('가벼운 작업 때는 팬이 멈춘다(0dB) — 조용하다.')
    if (s.low_profile) out.push('높이가 낮은 카드라 슬림 케이스에 들어간다.')
  }
  if (v.distributor?.warranty_years) out.push(`${v.distributor.name} 유통 — 국내 무상 보증 ${v.distributor.warranty_years}년.`)
  if (v.form) out.push(`${v.form.label} — ${v.form.warranty_years ? `국내 A/S ${v.form.warranty_years}년` : v.form.official ? '국내 정식 유통' : '국내 정식 A/S 가 없다'}.`)
  if (part.category !== 'gpu' && part.category !== 'cpu') return out
  // 칩 자체가 왜 많이 팔리나 — 같은 등급 안에서 성능 1점당 가격 순위
  const tier = tierOf(part, data.categories)
  const peers = data.parts
    .filter((p) => p.category === part.category && p.status === 'current' && tierOf(p, data.categories)?.tier === tier?.tier)
    .map((p) => ({ p, v: (priceOf(p, data.prices) ?? Infinity) / (p.perf.index || 1) }))
    .filter((x) => Number.isFinite(x.v))
    .sort((a, b) => a.v - b.v)
  const at = peers.findIndex((x) => x.p.id === part.id)
  if (at >= 0 && peers.length > 1) {
    out.push(
      at === 0
        ? `칩 자체도 ${tier?.tier} 등급 ${peers.length}개 중 성능 1점당 가장 싸다 — 이 급을 사는 사람이 몰리는 이유다.`
        : `칩은 ${tier?.tier} 등급 ${peers.length}개 중 성능 1점당 ${at + 1}번째로 싸다.`,
    )
  }
  return out
}

/** 판매처 링크 — 다나와는 그 매물, 나머지는 같은 이름으로 검색한 결과다(긁지 않고 링크만 건다) */
export function shopLinks(v: Variant, guide: Guide | null): { label: string; url: string }[] {
  const cheapest = [...v.offers].sort((a, b) => a.price - b.price)[0]
  let q = v.model?.name ?? cheapest.name
  for (const d of guide?.distributors ?? []) for (const a of [d.name, ...(d.aliases ?? [])]) q = q.replace(a, '')
  q = q.replace(/\(÷\d+\)/, '').replace(/\s+/g, ' ').trim()
  const e = encodeURIComponent(q)
  return [
    { label: '다나와', url: cheapest.url },
    { label: '네이버쇼핑', url: `https://search.shopping.naver.com/search/all?query=${e}` },
    { label: '쿠팡', url: `https://www.coupang.com/np/search?q=${e}` },
  ]
}
