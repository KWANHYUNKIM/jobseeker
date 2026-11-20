import { useEffect, useState } from 'react'
import { docFetch } from '../../../api/client'

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
      // 옛 공고의 전문이 남아 있을 때만 — 줄 단위로 더해진 것·빠진 것
      added_lines?: string[]
      removed_lines?: string[]
    }

/** 왜 다시 올렸나. label 은 바뀐 사실, why 는 그로부터 읽은 추정이다. */
export interface RepostReason {
  code: string
  label: string
  why: string
  weight: number
}

export interface Repost {
  company: string
  title: string
  url: string
  site: string
  rounds: number // 몇 번째 모집인가 (2 이상)
  prev_deadline: string
  now_deadline: string
  prev_seen: string
  now_seen: string
  changes: RepostChange[]
  tech_stack: string[]
  // 아래는 2026-11 에 더한 것 — 그 전 파일에는 없다
  prev_url?: string
  gap_days?: number | null // 옛 공고 마감(모르면 등록)부터 새 공고까지 며칠
  reasons?: RepostReason[] // 강한 이유가 앞
  basis?: 'pair' | 'history' // 옛 공고 전문과 비교했나, 히스토리 판본(길이·해시)과 비교했나
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
    top_reasons?: [string, number][] // 자리마다 가장 강한 이유 하나씩 센 것
  }
}

export function useReposts() {
  const [data, setData] = useState<RepostsFile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    docFetch('/reposts.json')
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
