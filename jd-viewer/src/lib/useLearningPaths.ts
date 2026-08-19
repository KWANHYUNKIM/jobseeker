import { useEffect, useState } from 'react'

// public/blog_guides.json  — bin/build_blog_guides.py
// public/inflearn_courses.json — bin/build_inflearn.py

export interface GuidePost {
  title: string
  company: string
  url: string
  published: string
  score: number // 방향과의 코사인
  edge: number // score − 모든 개념 평균(= 이 주제에 '유독' 가까운 정도)
  tech: string[]
}

export interface GuideConcept {
  name: string
  jobs: number
  job_pct: number
  sharpness: number // 낮으면 그 요구는 어디에나 있어 방향이 흐리다
  tech: { name: string; n: number }[]
  posts: GuidePost[]
}

export interface GuideTech {
  name: string
  jobs: number
  posts: GuidePost[]
}

export interface BlogGuidesFile {
  generated_at: string
  method: string
  jobs: number
  posts: number
  concepts: GuideConcept[]
  techs: GuideTech[]
}

export interface Course {
  id: number
  slug: string
  url: string
  title: string
  description: string
  students: number
  likes: number
  duration_sec: number
  level: string
  level_ko: string
  skills: string[]
  abilities: string[]
  targets: string[]
  prerequisites: string[]
  instructors: string[]
  price_regular: number | null
  price_pay: number | null
  is_free: boolean
  published_at: string
  updated_at: string
  is_new: boolean
  is_best: boolean
}

export interface CourseTech {
  tech: string
  demand_pct: number
  trend_delta: number | null
  candidates: number
  courses: Course[]
  paid_count: number
  levels: string[]
}

export interface InflearnFile {
  generated_at: string
  source: string
  tech_count: number
  techs: CourseTech[]
}

function useJson<T>(path: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch(path)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - ${path}`)
        return r.json()
      })
      .then((d: T) => {
        if (!cancelled) {
          setData(d)
          setLoading(false)
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [path])

  return { data, loading, error }
}

export const useBlogGuides = () => useJson<BlogGuidesFile>('/blog_guides.json')
export const useInflearn = () => useJson<InflearnFile>('/inflearn_courses.json')
