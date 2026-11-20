import { useEffect, useState } from 'react'
import { docFetch } from '../../../api/client'

// public/lectures/index.json + public/lectures/items/<id>.json
//   — lecture-engine/PROMPT.md 가 영상 한 편씩 쌓고, lecture-engine/schema.json 이 형식의 단일 소스.
// 영상을 자막(말)과 장면(판서·슬라이드)으로 읽고 우리 말로 다시 쓴 노트다. 원본은 링크로만 잇는다.

export interface LectureCard {
  id: string
  title: string
  title_ko: string
  school?: string
  code?: string
  term?: string
  speaker?: string
  topic: string
  tags: string[]
  level: '입문' | '중급' | '심화'
  one_line: string
  duration_sec?: number
  published?: string
  views?: number
  url: string
  platform: string
  thumbnail?: string | null
  chapters: number
  written_at: string
}

export interface LectureIndex {
  generated_at: string
  count: number
  topics: { key: string; label: string; count: number }[]
  items: LectureCard[]
}

/** 챕터 하나 = 교재의 한 절. 요점(points)은 복습용이고 본문(explain)이 공부하는 곳이다. */
export interface Chapter {
  start: number
  title: string
  points: string[]
  on_screen?: string
  explain?: string[]
  formulas?: { expr: string; meaning: string }[]
  example?: { title: string; body: string }
  code?: { lang: string; src: string; note?: string }
  diagram?: { title?: string; code: string }
  pitfalls?: string[]
  check?: { q: string; a: string }[]
}

export interface Lecture {
  id: string
  source: { platform: string; url: string; channel: string; published?: string; duration_sec?: number; views?: number }
  course: { school: string; code?: string; term?: string; lecture_no?: string; speaker?: string }
  title: string
  title_ko: string
  topic: string
  tags?: string[]
  level: string
  one_line: string
  summary: string[]
  why_now?: string
  chapters: Chapter[]
  concepts: { term: string; explain: string; at?: number }[]
  trends?: { claim: string; evidence?: string; at?: number }[]
  study: {
    prereq?: string[]
    steps: { do: string; why?: string }[]
    practice?: string[]
    resources?: { title: string; url: string }[]
  }
  jobs?: { roles?: string[]; skills?: string[] }
  related?: string[]
  materials: { transcript: string; frames?: number; every_sec?: number }
  written_at: string
}

function useJson<T>(path: string | null) {
  const [state, setState] = useState<{ data: T | null; loading: boolean; error: string | null }>({
    data: null,
    loading: !!path,
    error: null,
  })
  useEffect(() => {
    if (!path) return
    const ac = new AbortController()
    setState({ data: null, loading: true, error: null })
    docFetch(path, { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
        return r.json() as Promise<T>
      })
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setState({ data: null, loading: false, error: e.message })
      })
    return () => ac.abort()
  }, [path])
  return state
}

export const useLectureIndex = () => useJson<LectureIndex>('/lectures/index.json')
export const useLecture = (id: string | null) => useJson<Lecture>(id ? `/lectures/items/${id}.json` : null)

/** 3725 → '1:02:05' */
export function hms(sec?: number): string {
  if (sec == null) return ''
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`
}

/** 원본 영상의 그 자리 — 유튜브는 `&t=초` */
export function at(url: string, sec?: number): string {
  if (sec == null || !url.includes('youtube.com')) return url
  return `${url}${url.includes('?') ? '&' : '?'}t=${sec}s`
}
