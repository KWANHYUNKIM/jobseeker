export type Site = 'wanted' | 'jumpit' | 'jobkorea' | 'saramin' | 'dev'

export interface Job {
  site: Site
  idx: number
  pid: string
  company: string
  title: string
  url: string
  career: string
  location: string
  tech_stack: string[]
  main_tasks: string
  qualifications: string
  preferences: string
  benefits: string
  full_jd: string
}

// ── 회사 기술스택 분석 (company_stacks.json) ───────────────────────────
export interface TechCount {
  name: string
  count: number
}

export interface CompanyDomain {
  name: string
  score: number
  evidence: string[]
}

export interface CompanyArch {
  label: string
  why: string
}

export interface CompanyPosting {
  title: string
  url: string
  site: string
}

export interface CareerRoadmapStage {
  stage: string
  goal: string
  techs: string[]
  tips: string[]
}

export interface CareerBlog {
  title: string
  url: string
  company: string
  country: string
  why: string
}

export interface CareerGuide {
  wants: string[]
  roadmap: CareerRoadmapStage[]
  tasks: string[]
  study_blogs: CareerBlog[]
}

export interface CompanyStack {
  name: string
  norm: string
  size: string
  size_alias: string | null
  posting_count: number
  sites: string[]
  roles: Record<string, number>
  top_tech: TechCount[]
  tech_categories: Record<string, TechCount[]>
  domains: CompanyDomain[]
  architecture: CompanyArch[]
  titles: string[]
  postings: CompanyPosting[]
  summary: string
  career_guide?: CareerGuide
  homepage?: string | null
  homepage_desc?: string | null
  homepage_tech?: string[]
}

export interface CompanyStacksFile {
  generated_at: string
  total_jobs: number
  company_count: number
  min_posting: number
  companies: CompanyStack[]
}

// ── 개발 트렌드 (trends.json) ──────────────────────────────────────────
export interface TrendDay {
  date: string
  total: number
  tech: Record<string, number> // 기술 → 그날 공고 중 언급 건수
}

export interface TrendMover {
  tech: string
  from_pct: number
  to_pct: number
  delta: number // 비중 변화(%p)
}

export interface TrendsFile {
  generated_at: string
  span: { from: string; to: string; days: number }
  tracked: string[]
  days: TrendDay[]
  movers: { up: TrendMover[]; down: TrendMover[] }
}

// ── 기술 관계·맥락 (tech_relations.json) ───────────────────────────────
export interface RelatedTech {
  name: string
  layer: string
  count: number
  pct: number // 이 기술 공고 중 함께 쓰인 비율
}

export interface TechRelation {
  name: string
  layer: string
  count: number
  pct_jobs: number
  related: RelatedTech[]
  context: string | null // LLM: 어디서·왜 쓰이는지(마크다운)
}

export interface DomainInsight {
  domain: string
  techs: string[]
  why: string // 마크다운
}

export interface TechRelationsFile {
  generated_at: string
  total_jobs: number
  techs: TechRelation[]
  domains: DomainInsight[]
}

// ── 모집 캘린더 (job_calendar.json) ────────────────────────────────────
export interface CalendarItem {
  company: string
  title: string
  url: string
  site: string
  career: string
  tech_stack: string[]
  start: string | null // 모집 시작일 ISO
  deadline: string | null // 마감일 ISO
  always_open: boolean // 상시채용
}

export interface CalendarFile {
  generated_at: string
  total: number
  dated: number
  always_open: number
  no_info: number
  items: CalendarItem[]
}

// ── 기술 블로그 (tech_blogs.json) ──────────────────────────────────────
export interface BlogPost {
  key: string
  company: string
  country: string
  title: string
  url: string
  published: string
  published_ts: number
  summary: string
  tech_stack: string[]
  categories: string[]
  tags: string[]
  lang: string
  content_id?: string
}

// 글별 본문/번역 (blog_content/<id>.json)
export interface BlogContent {
  url: string
  title: string
  lang: string
  format?: string
  content: string
  content_ko: string
  translated: boolean
  chars: number
}

export interface BlogSource {
  company: string
  country: string
  count: number
}

export interface BlogFile {
  generated_at: string
  total: number
  sources: BlogSource[]
  categories: string[]
  tag_categories: Record<string, string>
  posts: BlogPost[]
}

// ── 기술 스택 레이더 (company_tech_radar.json) ─────────────────────────
export interface RadarStack {
  backend: string[]
  frontend: string[]
  data: string[]
  infra: string[]
}

export interface GithubRepo {
  name: string
  url: string
  desc: string
  lang: string
  stars?: number
}

export interface Github {
  org: string
  repos?: GithubRepo[]
}

// 회사 기술이 '실제로 어떻게 작동하는지' 심화 해설 — 토픽별 누적(loop 가 계속 덧붙임).
export interface DeepDiveSection {
  topic: string
  body: string // 마크다운
}

// ── 아키텍처 토론 (멀티 에이전트: 설계자↔검토자 + 정리자) ──────────────
export interface ArchCandidate {
  name: string // "변형 A: 이벤트 소싱 중심"
  summary: string
  diagram?: string // mermaid (선택)
  pros: string[]
  cons: string[]
}

export interface DebateTurn {
  round: number
  role: 'architect' | 'critic' | 'synthesizer'
  text: string // 마크다운
}

export interface DebateVerdict {
  chosen: string // 어떤 후보/하이브리드로 합의했는지
  rationale: string // 마크다운
  key_insights: string[]
  open_questions: string[]
}

export interface Debate {
  generated_at: string
  rounds: number
  architectures: ArchCandidate[] // 여러 아키텍처 후보
  transcript: DebateTurn[] // 에이전트 대화 전사
  verdict: DebateVerdict // 합의 결론
}

// ── 채용 전형 가이드 (공개 절차·일반 패턴 기반, 사적 후기 스크래핑 아님) ──
export interface InterviewStage {
  name: string
  format?: string
  duration?: string
  detail: string
}

// 공개 블로그/커리어 페이지의 면접 후기(링크+요약). 사적 후기 사이트는 수집하지 않음.
export interface InterviewReview {
  title: string
  url: string
  summary: string
  source: string // 블로그/플랫폼 이름(예: velog, tistory)
  date?: string
}

export interface Interview {
  process: InterviewStage[]
  focus: string[] // 이 회사가 보는 핵심 역량
  tips: string[] // 지원자 준비 팁
  difficulty?: string
  sources: string[]
  reviews?: InterviewReview[] // 공개 면접 후기(크롤 루프가 누적)
}

export interface RadarCompany {
  key: string
  name: string
  country: string
  domain: string
  languages: string[]
  stack: RadarStack
  architecture: string[]
  diagram?: string
  why_language: string
  why_architecture: string
  summary: string
  deep_dive?: DeepDiveSection[]
  debate?: Debate
  interview?: Interview
  github?: Github
  sources: string[]
  research_status: 'seed' | 'llm-refined'
  updated_at: string
}

export interface RadarCount {
  code?: string
  name?: string
  count: number
}

// 도메인별 공통 기술 집계 — 한 산업 도메인을 대표하는 기술 빈도
export interface RadarTechCount {
  name: string
  count: number
}

// 상위 산업 도메인 그룹 — 그 도메인이 어떤 기술스택으로 이루어지는지 집계
export interface DomainGroup {
  name: string
  count: number
  companies: string[]
  subdomains: string[]
  languages: RadarTechCount[]
  stack: {
    backend: RadarTechCount[]
    frontend: RadarTechCount[]
    data: RadarTechCount[]
    infra: RadarTechCount[]
  }
  architecture: RadarTechCount[]
}

export interface RadarFile {
  generated_at: string
  total: number
  countries: RadarCount[]
  domains: RadarCount[]
  refined: number
  domain_groups: DomainGroup[]
  companies: RadarCompany[]
}

export type CareerBucket =
  | '신입/무관'
  | '1-2년'
  | '3-4년'
  | '5-7년'
  | '8년+'
  | '정보없음'

export const CAREER_BUCKETS: CareerBucket[] = [
  '신입/무관',
  '1-2년',
  '3-4년',
  '5-7년',
  '8년+',
  '정보없음',
]
