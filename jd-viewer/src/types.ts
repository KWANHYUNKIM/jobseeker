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
