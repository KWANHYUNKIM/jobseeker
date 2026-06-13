// 기술스택 확장 분석
// company_stacks.json(이미 로드된 CompanyStack[])에서 클라이언트 계산:
//  1) 기술 → 회사 역인덱스 (어떤 회사가 이 기술을 쓰나)
//  2) 기술 동시출현 (회사 단위) — confidence/lift 로 "확장 추천" 산출
//  3) 카테고리/기술 메타 (선택 UI 용)
// 정적: 직군별 큐레이션 로드맵.

import type { CompanyStack } from '../types'

export const CAT_ORDER = [
  '언어',
  '백엔드',
  '프론트엔드',
  '모바일',
  '데이터베이스',
  '인프라/DevOps',
  '펌웨어/임베디드',
  'AI/ML',
  '데이터',
  '협업/도구',
  '기타',
]

export const CAT_COLOR: Record<string, string> = {
  언어: '#c084fc',
  백엔드: '#60a5fa',
  프론트엔드: '#34d399',
  모바일: '#fbbf24',
  데이터베이스: '#22d3ee',
  '인프라/DevOps': '#fb923c',
  '펌웨어/임베디드': '#a78bfa',
  'AI/ML': '#f472b6',
  데이터: '#2dd4bf',
  '협업/도구': '#94a3b8',
  기타: '#6b7280',
}

export interface TechNode {
  name: string
  category: string
  companyCount: number // 이 기술을 쓰는 회사 수
  postingCount: number // 공고 누적(회사별 count 합)
}

export interface CompanyRef {
  name: string
  norm: string
  size: string
  count: number // 이 회사에서 해당 기술 공고 수
  domains: string[]
}

export interface CoocItem {
  name: string
  category: string
  coCount: number // 두 기술을 함께 쓰는 회사 수
  confidence: number // P(b|a) = coCount / count(a)
  lift: number // confidence / P(b)
}

export interface ExpansionIndex {
  techs: TechNode[] // companyCount 내림차순
  byCategory: Record<string, TechNode[]>
  companiesByTech: Record<string, CompanyRef[]> // key = tech name
  coocByTech: Record<string, CoocItem[]> // key = tech name, lift 내림차순
  categoryOf: Record<string, string>
  totalCompanies: number
}

const MIN_SUPPORT = 3 // 동시출현 최소 회사 수 (노이즈 컷)
const MIN_LIFT = 1.2 // 연관도 하한 — 어디서나 쓰이는 기술(lift≈1) 제거

export function buildExpansionIndex(companies: CompanyStack[]): ExpansionIndex {
  const total = companies.length
  const categoryOf: Record<string, string> = {}
  const companyCount: Record<string, number> = {}
  const postingCount: Record<string, number> = {}
  const companiesByTech: Record<string, CompanyRef[]> = {}
  // 회사 단위 동시출현: cooc[a][b] = 두 기술 모두 쓰는 회사 수
  const cooc: Record<string, Record<string, number>> = {}

  for (const c of companies) {
    // 회사가 가진 (기술, count) 모음 — 같은 기술이 여러 카테고리에 있진 않지만 방어적으로 합산
    const techCount: Record<string, number> = {}
    for (const cat of Object.keys(c.tech_categories)) {
      for (const t of c.tech_categories[cat]) {
        if (!(t.name in categoryOf)) categoryOf[t.name] = cat
        techCount[t.name] = (techCount[t.name] ?? 0) + t.count
      }
    }
    const names = Object.keys(techCount)
    const domains = c.domains.map((d) => d.name)
    for (const name of names) {
      companyCount[name] = (companyCount[name] ?? 0) + 1
      postingCount[name] = (postingCount[name] ?? 0) + techCount[name]
      ;(companiesByTech[name] ??= []).push({
        name: c.name,
        norm: c.norm,
        size: c.size,
        count: techCount[name],
        domains,
      })
    }
    // 동시출현 (정렬 불필요, 양방향 기록)
    for (let i = 0; i < names.length; i++) {
      const a = names[i]
      const ra = (cooc[a] ??= {})
      for (let j = 0; j < names.length; j++) {
        if (i === j) continue
        const b = names[j]
        ra[b] = (ra[b] ?? 0) + 1
      }
    }
  }

  const techs: TechNode[] = Object.keys(companyCount).map((name) => ({
    name,
    category: categoryOf[name] ?? '기타',
    companyCount: companyCount[name],
    postingCount: postingCount[name],
  }))
  techs.sort((x, y) => y.companyCount - x.companyCount || y.postingCount - x.postingCount)

  const byCategory: Record<string, TechNode[]> = {}
  for (const t of techs) (byCategory[t.category] ??= []).push(t)

  // 회사 목록은 공고수 내림차순
  for (const k of Object.keys(companiesByTech)) {
    companiesByTech[k].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }

  // 동시출현 → 확장 추천: lift 로 "유난히 함께 쓰는" 기술 우선, 최소 지지 회사수 컷
  const coocByTech: Record<string, CoocItem[]> = {}
  for (const a of Object.keys(cooc)) {
    const baseA = companyCount[a]
    const items: CoocItem[] = []
    for (const b of Object.keys(cooc[a])) {
      const co = cooc[a][b]
      if (co < MIN_SUPPORT) continue
      const conf = co / baseA
      const pB = companyCount[b] / total
      const lift = pB > 0 ? conf / pB : 0
      if (lift < MIN_LIFT) continue
      items.push({ name: b, category: categoryOf[b] ?? '기타', coCount: co, confidence: conf, lift })
    }
    // 동반율(confidence) 우선 — 실속 있는 추천. 동률이면 동반 회사수
    items.sort((x, y) => y.confidence - x.confidence || y.coCount - x.coCount)
    coocByTech[a] = items
  }

  return { techs, byCategory, companiesByTech, coocByTech, categoryOf, totalCompanies: total }
}
