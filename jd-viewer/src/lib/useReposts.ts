import { useEffect, useState } from 'react'

// public/reposts.json — bin/build_reposts.py
// 같은 자리가 마감됐다가 다시 올라온 것과, 그 사이 무엇이 바뀌었는지.

export type RepostChange =
  | { field: string; kind: 'value'; from: string; to: string }
  | { field: string; kind: 'list'; added: string[]; removed: string[] }
  | {
      field: string
      kind: 'text'
      // 한쪽이 0자 = 그 판의 본문을 못 긁은 것. 변경이 아니라 비교 불가다.
      missing?: boolean
      from_len: number
      to_len: number
      to_excerpt: string
    }

export interface Repost {
  company: string
  title: string
  url: string
  site: string
  rounds: number // 기록된 판 수 (2 이상이면 최소 한 번 재공고)
  prev_deadline: string
  now_deadline: string
  prev_seen: string
  now_seen: string
  changes: RepostChange[]
  tech_stack: string[]
}

export interface RepostsFile {
  generated_at: string
  history_versions: number
  tracked_positions: number
  reposts: Repost[]
  summary: {
    count: number
    changed_fields: [string, number][]
    career_moves: Record<string, number>
  }
}

export function useReposts() {
  const [data, setData] = useState<RepostsFile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/reposts.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - reposts.json`)
        return r.json()
      })
      .then((d: RepostsFile) => {
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
  }, [])

  return { data, loading, error }
}
