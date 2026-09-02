import { useEffect, useMemo, useState } from 'react'
import { normalizeCompany } from './companyMark'

// public/guide/index.json + public/guide/companies/<slug>.json
//   — guide-engine/PROMPT.md 가 매 사이클 갱신, guide-engine/schema.json 이 형식의 단일 소스.
//
// 역설계(useReveng)와 나눠 둔 이유: 저긴 "이 회사가 어떻게 만들어졌나", 여긴 "내가
// 저기 들어가려면 뭘 하나"다. 회사도 큐도 겹치지 않아서 한 파일에 담으면 둘 다 얇아진다.
//
// 공고와 브리핑은 **회사명이 아니라 정규화한 회사명(aliases)** 으로 잇는다. 공고마다
// (주)·주식회사·영문 병기가 제각각이라, 원문 그대로 맞추면 같은 회사가 서로 다른 회사가 된다.

export type Confidence = 'confirmed' | 'inferred' | 'unknown'
export type Priority = 'core' | 'high' | 'nice'
export type StudyFrom = 'qualification' | 'preference' | 'task'

export interface Source {
  title: string
  url: string
  publisher?: string
  date?: string
  summary?: string
}

export interface GuideResource {
  title: string
  url: string
  kind?: 'docs' | 'post' | 'talk' | 'paper' | 'repo' | 'course'
  note?: string
}

export interface StudyItem {
  topic: string
  from: StudyFrom
  /** 공고 원문 문장 그대로 — 이 문자열로 JD 본문을 하이라이트한다. */
  quote: string
  priority: Priority
  why: string
  gap_check: string
  drill: string
  hours?: number
  resources?: GuideResource[]
}

/**
 * 본문 하이라이트가 실제로 쓰는 것만 추린 형태. `StudyItem`(사람이 쓴 것)과
 * `AutoStudyItem`(공고에서 뽑은 것)은 나머지가 전혀 다르지만 **하이라이트에 필요한
 * 네 칸은 같다** — 본문 쪽이 넓은 타입을 요구하면 자동 브리핑 문장은 영영 못 켠다.
 */
export interface HighlightMark {
  quote: string
  topic: string
  priority: Priority
  from: StudyFrom
}

/** 자동 학습 항목을 하이라이트용으로 옮긴다. topic 은 찾은 기술 용어로 대신한다. */
export function autoMark(it: AutoStudyItem): HighlightMark {
  return {
    quote: it.quote,
    topic: it.topics.length ? it.topics.join(' · ') : '공고 문장',
    priority: it.priority,
    from: it.from,
  }
}

export interface EdgeItem {
  idea: string
  why: string
  effort?: string
}

export interface GuidePosting {
  url: string
  title: string
  site: string
  closed?: boolean
  verdict: string
  fit?: { must_have?: string[]; can_learn?: string[] }
  study?: StudyItem[]
  edge?: EdgeItem[]
  interview?: { process?: string; expect?: string[]; sources?: Source[] }
}

export interface SalaryBand {
  role: string
  level: string
  low: number
  high: number
  basis: 'posting' | 'public_data' | 'market'
  confidence?: Confidence
  sources?: Source[]
}

export interface Salary {
  unit?: string
  currency?: string
  as_of?: string
  bands?: SalaryBand[]
  equity?: string
  note?: string
  open_questions?: string[]
}

export interface PublicWork {
  title: string
  url: string
  kind?: 'talk' | 'post' | 'interview' | 'paper' | 'repo'
  date?: string
  summary?: string
}

export interface Person {
  name: string
  role: string
  why_public?: string
  public_work?: PublicWork[]
  leanings?: string[]
  what_it_means?: string
  confidence?: Confidence
  sources?: Source[]
}

export interface GuideDomain {
  name: string
  why: string
  what_to_know?: string[]
  confidence?: Confidence
  sources?: Source[]
}

/** 수익원 하나. domains 는 이 돈을 떠받치는 GuideDomain.name 들이다. */
export interface RevenueStream {
  name: string
  how: string
  weight?: string
  domains?: string[]
  confidence?: Confidence
  sources?: Source[]
}

export interface CompanyBrief {
  business?: string
  business_confidence?: Confidence
  business_sources?: Source[]
  scale?: { label: string; value: string; as_of?: string; confidence?: Confidence; sources?: Source[] }[]
  revenue?: RevenueStream[]
  domains?: GuideDomain[]
  signals?: { reading: string; evidence: string; so_what?: string; confidence?: Confidence }[]
}

export interface CompanyGuide {
  slug: string
  name: string
  name_en?: string
  aliases: string[]
  status: 'in_progress' | 'done'
  updated_at: string
  site?: string
  one_liner?: string
  company?: CompanyBrief
  salary?: Salary | null
  people?: Person[]
  postings?: GuidePosting[]
  open_questions?: string[]
}

// ── 자동 브리핑 (guide-engine/autoguide.py) ──────────────────────────────
// 손으로 쓴 브리핑이 없는 회사를 빈 화면으로 두지 않기 위한 **폴백**이다. 같은
// 스키마가 아니다 — 저긴 사람이 판단해 쓴 글이고 여긴 정규식이 공고에서 뽑은 사실이라,
// `why`·`drill`·`verdict` 가 아예 없다. 타입을 합치면 화면이 빈 칸을 "아직 안 쓴 것"
// 으로 그리게 되므로 **일부러 따로 둔다.**

export interface AutoStudyItem {
  /** 공고 원문 문장 그대로 — 손으로 쓴 브리핑과 같이 이 문자열로 본문을 하이라이트한다. */
  quote: string
  from: StudyFrom
  priority: Priority
  /** 문장에서 찾은 기술 용어. 없을 수 있다(문장이 기술 용어를 안 담은 경우). */
  topics: string[]
}

export interface AutoPosting {
  url: string
  title: string
  site: string
  closed?: boolean
  career?: { raw: string; min_years: number | null; max_years: number | null; kind: string } | null
  location?: string
  tech_stack?: string[]
  /** 계약직·프리랜서·파견·고객사상주 — 학습 계획의 전제가 달라지는 표기. */
  employment_flags?: string[]
  has_body?: boolean
  study?: AutoStudyItem[]
}

export interface AutoFact {
  label: string
  value: string
  quote: string
  source_url: string
  seen_in: number
  of_postings: number
}

export interface AutoSalary {
  low: number
  high: number | null
  unit: string
  /** '이상' 이면 low 는 하한이지 밴드가 아니다. */
  bound: string
  quote: string
  url: string
  title: string
  career?: string
}

export interface AutoDupGroup {
  reason: string
  confidence: Confidence
  postings: { url: string; site: string; title: string }[]
}

export interface AutoGuide {
  slug: string
  name: string
  aliases: string[]
  generator: string
  generated_at: string
  counts: {
    postings: number
    active: number
    closed: number
    with_body: number
    distinct_active: number
    study_items: number
  }
  facts: Record<string, AutoFact>
  salary_mentions: AutoSalary[]
  tech_stack: { name: string; count: number }[]
  duplicates: AutoDupGroup[]
  postings: AutoPosting[]
  /** 코드가 못 채우는 칸과, 채우려면 뭘 봐야 하는지. */
  gaps: { field: string; needs: string }[]
}

interface AutoIndexEntry {
  slug: string
  name: string
  aliases: string[]
}

interface IndexEntry {
  slug: string
  name: string
  aliases: string[]
  status: 'in_progress' | 'done'
  postings: number
  study_items: number
  updated_at: string
}

interface IndexFile {
  updated_at: string
  companies: IndexEntry[]
}

// 목록은 앱당 한 번, 상세는 열어 본 회사만. 브리핑이 몇백 곳이 돼도 공고 하나 여는
// 비용은 파일 두 개로 고정된다.
let indexPromise: Promise<IndexFile> | null = null
const fileCache = new Map<string, Promise<CompanyGuide | null>>()

function loadIndex(): Promise<IndexFile> {
  if (!indexPromise) {
    indexPromise = fetch('/guide/index.json')
      .then((r) => (r.ok ? r.json() : { updated_at: '', companies: [] }))
      .catch(() => ({ updated_at: '', companies: [] }))
  }
  return indexPromise
}

function loadCompany(slug: string): Promise<CompanyGuide | null> {
  let p = fileCache.get(slug)
  if (!p) {
    p = fetch(`/guide/companies/${slug}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<CompanyGuide>) : null))
      .catch(() => null)
    fileCache.set(slug, p)
  }
  return p
}

// 자동 브리핑도 같은 방식으로 목록 한 번 + 상세는 열어 본 회사만. 인덱스는 손으로 쓴
// 것(20곳)보다 훨씬 크지만(800곳) 압축을 빼고 한 줄로 써서 200KB 안쪽이다.
let autoIndexPromise: Promise<AutoIndexEntry[]> | null = null
const autoFileCache = new Map<string, Promise<AutoGuide | null>>()

function loadAutoIndex(): Promise<AutoIndexEntry[]> {
  if (!autoIndexPromise) {
    autoIndexPromise = fetch('/guide/auto/index.json')
      .then((r) => (r.ok ? r.json() : { companies: [] }))
      .then((d) => (d.companies || []) as AutoIndexEntry[])
      .catch(() => [])
  }
  return autoIndexPromise
}

function loadAuto(slug: string): Promise<AutoGuide | null> {
  let p = autoFileCache.get(slug)
  if (!p) {
    p = fetch(`/guide/auto/companies/${slug}.json`)
      .then((r) => (r.ok ? (r.json() as Promise<AutoGuide>) : null))
      .catch(() => null)
    autoFileCache.set(slug, p)
  }
  return p
}

export interface JobGuideResult {
  loading: boolean
  /** 이 회사의 브리핑. 아직 안 쓴 회사면 null. */
  guide: CompanyGuide | null
  /** 이 공고에 딱 붙는 부분. 회사 브리핑은 있는데 이 공고는 아직이면 null. */
  posting: GuidePosting | null
  /** 손으로 쓴 브리핑이 이 공고를 아직 안 덮었을 때만 채워지는 폴백. */
  auto: AutoGuide | null
  autoPosting: AutoPosting | null
}

/** 공고 하나에 붙는 취업 브리핑. 회사명 → aliases → slug → 파일. */
export function useJobGuide(company: string, url: string): JobGuideResult {
  const [guide, setGuide] = useState<CompanyGuide | null>(null)
  const [auto, setAuto] = useState<AutoGuide | null>(null)
  const [loading, setLoading] = useState(true)
  const norm = useMemo(() => normalizeCompany(company), [company])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setGuide(null)
    setAuto(null)

    // 손으로 쓴 브리핑을 먼저 본다. 자동 브리핑은 **그게 이 공고를 못 덮을 때만**
    // 받는다 — 둘을 늘 같이 받으면 이미 잘 쓰인 회사에서 800곳짜리 인덱스를 괜히
    // 받게 되고, 화면에는 쓰이지도 않는다.
    loadIndex()
      .then((idx) => {
        const hit = (idx.companies || []).find((c) => (c.aliases || []).includes(norm))
        return hit ? loadCompany(hit.slug) : null
      })
      .then(async (doc) => {
        if (cancelled) return
        setGuide(doc)
        const covered = (doc?.postings || []).some((p) => p.url === url)
        if (!covered) {
          const rows = await loadAutoIndex()
          const hit = rows.find((c) => (c.aliases || []).includes(norm))
          const a = hit ? await loadAuto(hit.slug) : null
          if (!cancelled) setAuto(a)
        }
        if (!cancelled) setLoading(false)
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [norm, url])

  const posting = useMemo(
    () => (guide?.postings || []).find((p) => p.url === url) || null,
    [guide, url],
  )
  const autoPosting = useMemo(
    () => (auto?.postings || []).find((p) => p.url === url) || null,
    [auto, url],
  )

  return { loading, guide, posting, auto, autoPosting }
}

export const PRIORITY_LABEL: Record<Priority, string> = {
  core: '필수',
  high: '강점',
  nice: '우대',
}

// 세 등급을 색으로 나눈다. 필수는 브랜드색으로 끌어당기고, 우대는 뒤로 물린다 —
// 다 같은 색이면 아홉 개 항목 중 뭘 먼저 할지가 화면에서 안 읽힌다.
export const PRIORITY_COLOR: Record<Priority, string> = {
  core: 'var(--color-accent)',
  high: 'var(--color-sky-400)',
  nice: 'var(--color-faint)',
}

export const FROM_LABEL: Record<StudyFrom, string> = {
  qualification: '자격 요건',
  preference: '우대 사항',
  task: '주요 업무',
}

/** core → high → nice. 같은 등급 안에서는 쓴 순서를 지킨다(엔진이 중요한 순으로 쓴다). */
export function sortStudy(items: StudyItem[]): StudyItem[] {
  const rank: Record<Priority, number> = { core: 0, high: 1, nice: 2 }
  return [...items].sort((a, b) => rank[a.priority] - rank[b.priority])
}
