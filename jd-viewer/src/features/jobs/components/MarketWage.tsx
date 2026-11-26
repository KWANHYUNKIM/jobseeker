import { useEffect, useState } from 'react'
import { apiGet } from '../../../api/client'

// 연차별 시장 시세 — 고용노동부 고용형태별노동실태조사(KOSIS)를 crawl_company_facts `wage` 가 DB market_wage·market_wage_size 에 쓰고,
// 뷰어 API `/api/market-wage` 가 준다(정적 파일 없음 — API 가 안 되면 이 칸을 그리지 않는다).
// 회사별 연차 연봉은 공개된 곳이 없어서, 이 직무의 직종 × 경력년수 전국 값과 이 회사 규모 × 대졸 × 나이 값을 나란히 보인다.

interface WageDoc {
  year: string
  source: { title: string; url: string }
  note: string
  occupations: Record<string, { name: string; careers: Record<string, { annual_만원?: number; workers?: number }> }>
  sizes_college: Record<string, Record<string, { annual_만원?: number; tenure_years?: number }>>
}

let wagePromise: Promise<WageDoc | null> | null = null
function loadWage(): Promise<WageDoc | null> {
  if (!wagePromise) {
    wagePromise = apiGet<WageDoc>('/api/market-wage').catch(() => null)
  }
  return wagePromise
}

/** 공고 제목 → 한국표준직업분류 직종. 모르면 소프트웨어 전문가(222). */
export function occupationOf(title: string): string {
  const t = title.toLowerCase()
  if (/디자이너|designer|ui\/?ux|ux|ui 디자인|bx|그래픽/.test(t)) return '28'
  if (/회로|fpga|asic|반도체|하드웨어 엔지니어|hw 엔지니어|pcb|아날로그|rf /.test(t)) return '234'
  if (/로봇|기계|메카|mechanical/.test(t)) return '235'
  if (/데이터|data|ml|머신러닝|딥러닝|ai |ai$|인공지능|llm|dba|database|네트워크|network|보안|security|인프라|infra|devops|sre|클라우드|cloud/.test(t)) return '223'
  if (/웹마스터|운영자|웹 운영|사이트 운영|전산 운영|헬프데스크/.test(t)) return '224'
  return '222'
}

const SIZE_KEYS: [number, string][] = [
  [9, '5~9인'],
  [29, '10~29인'],
  [99, '30~99인'],
  [299, '100~299인'],
  [499, '300~499인'],
  [Infinity, '500인이상'],
]
function sizeOf(employees?: number | null): string | null {
  if (!employees || employees < 5) return null
  return SIZE_KEYS.find(([max]) => employees <= max)![1]
}

const CAREERS: [string, string][] = [
  ['1년미만', '1년 미만(신입)'],
  ['1~3년미만', '1~3년'],
  ['3~5년미만', '3~5년'],
  ['5~10년미만', '5~10년'],
  ['10년이상', '10년 이상'],
]
const AGES = ['25~29', '30~34', '35~39', '40~44']

const man = (v?: number) => (v ? (v >= 10000 ? `${Math.floor(v / 10000)}억 ${(v % 10000).toLocaleString()}만원`.replace(' 0만원', '원') : `${v.toLocaleString()}만원`) : '–')

export function MarketWage({ title, employees }: { title: string; employees?: number | null }) {
  const [doc, setDoc] = useState<WageDoc | null>(null)
  useEffect(() => {
    let alive = true
    loadWage().then((d) => alive && setDoc(d))
    return () => {
      alive = false
    }
  }, [])
  if (!doc) return null
  const occ = doc.occupations[occupationOf(title)] ?? doc.occupations['222']
  if (!occ) return null
  const size = sizeOf(employees)
  const all = doc.sizes_college['전규모5인이상']
  const mine = size ? doc.sizes_college[size] : null
  // 규모 보정 — 같은 나이대의 '이 규모 ÷ 전 규모' 비율을 직종 값에 곱한다(통계 두 개를 이은 계산값).
  const ratio = mine && all && mine['전체']?.annual_만원 && all['전체']?.annual_만원 ? mine['전체'].annual_만원 / all['전체'].annual_만원 : null
  const max = Math.max(...CAREERS.map(([k]) => (occ.careers[k]?.annual_만원 ?? 0) * Math.max(1, ratio ?? 1)))
  return (
    <section>
      <h3 className="mb-1 text-[19px] font-bold text-[#272727]">연차별 시세</h3>
      <p className="mb-4 text-[13.5px] text-[#888]">
        회사별 연차 연봉은 공개 자료가 없어 정부 통계로 보입니다 — 한국은 신입 연봉에서 연차마다 오르는 구조라 이 줄로 가늠할 수 있습니다
      </p>
      <div className="rounded-lg border border-[#e4e4e4] px-4 py-3">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-[13.5px]">
          <b className="font-semibold text-[#272727]">{occ.name}</b>
          <span className="text-[#999]">전국 · {doc.year}년{ratio && size ? ` · 오른쪽은 ${size} 회사 보정` : ''}</span>
        </div>
        <ul className="flex flex-col gap-2">
          {CAREERS.map(([k, label]) => {
            const v = occ.careers[k]?.annual_만원
            const adj = v && ratio ? Math.round(v * ratio) : null
            return (
              <li key={k} className="grid grid-cols-[88px_1fr_auto] items-center gap-3 text-[14px]">
                <span className="text-[#555]">{label}</span>
                <span className="relative h-[10px] rounded-full bg-[#f1f3f7]">
                  <span className="absolute inset-y-0 left-0 rounded-full bg-[#b9c7ee]" style={{ width: `${((v ?? 0) / max) * 100}%` }} />
                  {adj && <span className="absolute inset-y-[2px] left-0 rounded-full bg-[#3657c8]" style={{ width: `${(adj / max) * 100}%`, opacity: 0.85 }} />}
                </span>
                <span className="whitespace-nowrap text-right tabular-nums text-[#272727]">
                  {man(v)}
                  {adj && <b className="ml-2 font-semibold text-[#3657c8]">≈ {man(adj)}</b>}
                </span>
              </li>
            )
          })}
        </ul>
      </div>
      {mine && (
        <div className="mt-3 rounded-lg border border-[#e4e4e4] px-4 py-3">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-[13.5px]">
            <b className="font-semibold text-[#272727]">{size} 회사 · 대졸 · 나이별</b>
            <span className="text-[#999]">전 직종 · 평균 근속연수 같이</span>
          </div>
          <ul className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-4">
            {AGES.map((a) => (
              <li key={a} className="text-[14px]">
                <div className="text-[#777]">{a}세</div>
                <div className="tabular-nums font-semibold text-[#272727]">{man(mine[a]?.annual_만원)}</div>
                <div className="text-[12px] text-[#999]">근속 {mine[a]?.tenure_years ?? '–'}년</div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-[13px] leading-[21px] text-[#888]">
        {doc.note} 직종은 공고 제목으로 골랐고{employees ? `, 회사 규모는 인원 ${employees.toLocaleString()}명 기준` : ''}입니다. 보정값(≈)은 두 통계를 이어 셈한 추정입니다.{' '}
        <a href={doc.source.url} target="_blank" rel="noopener noreferrer" className="text-[#3657c8]">
          {doc.source.title}
        </a>
      </p>
    </section>
  )
}
