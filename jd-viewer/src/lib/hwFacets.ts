import { checkBuild, type Build, type Category, type HwData, type Part } from './hardware'

// 조건 필터 — 조립 화면 왼쪽의 체크박스 줄(CPU 시리즈 · 칩셋 · 메모리 용량 …).
//
// 한 줄 안의 체크는 '이것 또는 저것'(OR), 줄끼리는 '그리고'(AND)다. 체크한 줄은 그 분류의 후보를
// 좁히고, 조합은 좁혀진 후보 안에서 다시 짜인다.
//
// 호환 표시는 **이미 체크한 다른 줄**을 기준으로 한다 — 자동으로 골라 둔 부품이 기준이 되면
// 인텔 조합에서 '라이젠' 을 누르는 것조차 막히게 된다(그 부품들은 새로 짜면 바뀌는데도).
// 사람이 못 박은 조건끼리만 부딪친다. 한 항목의 부품이 모두, 다른 줄에서 체크한 부품 모두와
// 부딪치면 그 항목은 '호환 안 됨' 이고, 부딪친 이유를 한 문장으로 돌려준다.

export interface FacetOption {
  value: string
  label: string
  /** 이 항목에 드는 부품. 'none' 은 그 분류를 비운다(내장 그래픽 = 그래픽카드 없음) */
  match: (p: Part) => boolean
  none?: boolean
}

export interface Facet {
  key: string
  label: string
  cat: Category
  hint: string
  options: FacetOption[]
}

const uniq = <T,>(xs: T[]) => [...new Set(xs)]

function band(w: number): string {
  if (w >= 1200) return '1200W 이상'
  if (w >= 1000) return '1000~1199W'
  if (w >= 800) return '800~999W'
  if (w >= 700) return '700~799W'
  if (w >= 600) return '600~699W'
  return '600W 미만'
}

/** 부품 목록에서 줄과 항목을 만든다 — 목록에 없는 값은 줄에 나오지 않는다. */
export function buildFacets(data: HwData): Facet[] {
  const of = (c: Category) => data.parts.filter((p) => p.category === c)
  const byValue = (c: Category, key: string, labelOf = (v: string) => v, order?: (a: string, b: string) => number) => {
    const vals = uniq(of(c).map((p) => String(p.specs[key])))
    if (order) vals.sort(order)
    return vals.map((v) => ({ value: v, label: labelOf(v), match: (p: Part) => String(p.specs[key]) === v }))
  }
  const num = (s: string) => parseInt(s.replace(/\D/g, ''), 10) || 0
  const cpuSeriesOrder = ['코어 울트라 시리즈2', '코어 14세대', '라이젠 9000 시리즈', '라이젠 7000 시리즈', '라이젠 5000 시리즈']
  const pos = (xs: string[]) => (a: string, b: string) => (xs.indexOf(a) + 1 || 99) - (xs.indexOf(b) + 1 || 99)

  return [
    { key: 'cpu-series', label: 'CPU 시리즈', cat: 'cpu', hint: '세대가 소켓을 정한다 — 소켓이 같아야 보드에 꽂힌다', options: byValue('cpu', 'series', undefined, pos(cpuSeriesOrder)) },
    { key: 'cpu-family', label: 'CPU 종류', cat: 'cpu', hint: '숫자가 클수록 코어가 많다', options: byValue('cpu', 'family', undefined, (a, b) => a.localeCompare(b, 'ko') ) },
    {
      key: 'chipset',
      label: '메인보드 칩셋',
      cat: 'mainboard',
      hint: '칩셋이 받는 CPU 소켓·메모리 종류가 정해져 있다',
      options: of('mainboard').map((p) => ({ value: p.id, label: `(${p.name.split(' ')[0] === 'Intel' ? '인텔' : 'AMD'}) ${p.name.split(' ').slice(1).join(' ')}`, match: (q: Part) => q.id === p.id })),
    },
    { key: 'mem-type', label: '메모리 종류', cat: 'ram', hint: 'DDR4 와 DDR5 는 홈 모양이 달라 서로 안 꽂힌다', options: byValue('ram', 'type') },
    {
      key: 'mem-total',
      label: '메모리 용량',
      cat: 'ram',
      hint: '두 장(듀얼 채널) 합계',
      options: uniq(of('ram').map((p) => Number(p.specs.capacity_gb) * 2))
        .sort((a, b) => b - a)
        .map((gb) => ({ value: String(gb), label: `${gb}GB`, match: (p: Part) => Number(p.specs.capacity_gb) * 2 === gb })),
    },
    {
      key: 'ssd-cap',
      label: 'SSD 용량',
      cat: 'ssd',
      hint: '운영체제·게임·빌드 캐시가 들어간다',
      options: uniq(of('ssd').map((p) => Number(p.specs.capacity_gb)))
        .sort((a, b) => b - a)
        .map((gb) => ({ value: String(gb), label: gb >= 1000 ? `${gb / 1000}TB` : `${gb}GB`, match: (p: Part) => Number(p.specs.capacity_gb) === gb })),
    },
    {
      key: 'gpu-kind',
      label: '그래픽 종류',
      cat: 'gpu',
      hint: '내장 그래픽은 CPU 안의 그래픽으로 화면을 낸다 — 게임·AI 에는 약하다',
      options: [
        { value: 'igpu', label: '내장 그래픽', match: () => false, none: true },
        { value: 'dgpu', label: '외장 그래픽', match: () => true },
      ],
    },
    { key: 'gpu', label: '그래픽 카드', cat: 'gpu', hint: '게임 fps 와 AI 속도를 거의 혼자 정한다', options: of('gpu').map((p) => ({ value: p.id, label: p.name.replace('GeForce ', '').replace('Radeon ', ''), match: (q: Part) => q.id === p.id })) },
    {
      key: 'psu-band',
      label: '파워 출력',
      cat: 'psu',
      hint: '그래픽카드 권장 파워보다 한 단계 여유 있게',
      options: uniq(of('psu').map((p) => band(Number(p.specs.watt))))
        .sort((a, b) => num(b) - num(a))
        .map((b) => ({ value: b, label: b, match: (p: Part) => band(Number(p.specs.watt)) === b })),
    },
    { key: 'cooler-type', label: 'CPU 쿨러', cat: 'cooler', hint: '공랭은 싸고 고장이 적다 · 수랭은 고전력 CPU 에', options: of('cooler').map((p) => ({ value: p.id, label: p.name, match: (q: Part) => q.id === p.id })) },
    { key: 'case-form', label: '케이스', cat: 'case', hint: '크기가 보드 규격·그래픽카드 길이를 정한다', options: of('case').map((p) => ({ value: p.id, label: p.name, match: (q: Part) => q.id === p.id })) },
  ]
}

export type Picked = Record<string, string[]>

/** 체크한 조건이 분류마다 허락하는 부품. 한 분류에 줄이 둘이면(시리즈·종류) 둘 다 맞아야 한다. */
export function allowedBy(facets: Facet[], picked: Picked, data: HwData): { allow: (p: Part) => boolean; noGpu: boolean } {
  const rules: ((p: Part) => boolean)[] = []
  let noGpu = false
  for (const f of facets) {
    const sel = f.options.filter((o) => picked[f.key]?.includes(o.value))
    if (!sel.length) continue
    if (sel.some((o) => o.none) && !sel.some((o) => !o.none)) {
      noGpu = true
      continue
    }
    const real = sel.filter((o) => !o.none)
    rules.push((p) => p.category !== f.cat || real.some((o) => o.match(p)))
  }
  void data
  return { allow: (p) => rules.every((r) => r(p)), noGpu }
}

/** 두 부품 묶음이 부딪치나 — 한쪽의 모든 부품이 다른 쪽의 모든 부품과 'error' 로 부딪치면 그 첫 이유. */
function clash(a: { cat: Category; parts: Part[]; none?: boolean }, b: { cat: Category; parts: Part[]; none?: boolean }, all: Part[]): string | null {
  const as: (Part | null)[] = a.none ? [null] : a.parts
  const bs: (Part | null)[] = b.none ? [null] : b.parts
  if (!as.length || !bs.length) return null
  let reason: string | null = null
  for (const x of as)
    for (const y of bs) {
      const build: Build = {}
      if (x) build[a.cat] = x.id
      if (y) build[b.cat] = y.id
      const errs = checkBuild(build, all).filter((c) => c.level === 'error' && c.cats.includes(a.cat) && c.cats.includes(b.cat) && c.cats.every((k) => k === a.cat || k === b.cat))
      if (!errs.length) return null // 하나라도 맞는 짝이 있으면 호환된다
      reason ??= errs[0].text
    }
  return reason
}

export interface OptionState {
  disabled: boolean
  reason: string | null
  against: string | null
}

/** 항목마다 — 다른 줄에서 체크한 조건과 부딪치나, 부딪치면 무엇과 왜 */
export function optionStates(facets: Facet[], picked: Picked, data: HwData): Map<string, OptionState> {
  const out = new Map<string, OptionState>()
  const pickedSets = facets
    .map((f) => {
      const sel = f.options.filter((o) => picked[f.key]?.includes(o.value))
      if (!sel.length) return null
      const none = sel.every((o) => o.none)
      return { f, label: sel.map((o) => o.label).join('·'), cat: f.cat, none, parts: none ? [] : data.parts.filter((p) => p.category === f.cat && sel.some((o) => !o.none && o.match(p))) }
    })
    .filter((x): x is NonNullable<typeof x> => !!x)
  for (const f of facets) {
    for (const o of f.options) {
      const mine = { cat: f.cat, none: o.none, parts: o.none ? [] : data.parts.filter((p) => p.category === f.cat && o.match(p)) }
      let st: OptionState = { disabled: false, reason: null, against: null }
      for (const other of pickedSets) {
        if (other.f.key === f.key) continue
        if (other.cat === f.cat) {
          // 같은 분류의 다른 줄(시리즈·종류) — 겹치는 부품이 없으면 함께 고를 수 없다
          if (!o.none && !other.none && !mine.parts.some((p) => other.parts.includes(p))) {
            st = { disabled: true, reason: "그 안에 이 종류의 제품이 없다", against: other.label }
            break
          }
          continue
        }
        const r = clash(mine, other, data.parts)
        if (r) {
          st = { disabled: true, reason: r, against: other.label }
          break
        }
      }
      out.set(`${f.key}:${o.value}`, st)
    }
  }
  return out
}
