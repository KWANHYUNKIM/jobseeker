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
