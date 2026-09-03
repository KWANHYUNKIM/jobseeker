import { useEffect, useState } from 'react'

/**
 * 행동 점수 — engagement.score 가 만든 public/engagement.json 을 읽는다.
 *
 * 추천을 두 가지 근거로 섞기 위해 있다.
 *   유사도(similar_jobs.json)  — 내용이 닮았다. 첫날부터 있다.
 *   행동(engagement.json)      — 사람들이 실제로 그다음에 봤다. 쌓여야 생긴다.
 *
 * 파일이 없으면(아직 아무도 안 눌렀거나 수집 서버가 안 떴거나) 조용히 비어 있는
 * 채로 동작한다. 그때 추천은 예전과 똑같이 유사도만으로 정렬된다 — 새 기능이
 * 없던 기능을 망가뜨리면 안 된다.
 */

export interface EngagementItem {
  /** 열린 횟수 */
  v: number
  /** 머문 시간 중앙값(초) */
  d: number
  /** 원본 공고로 넘어간 횟수 */
  o: number
  /** 추천을 눌러 들어온 횟수 */
  r: number
  /** 0~1 로 정규화한 점수 */
  score: number
}

export interface EngagementDoc {
  generated_at: string
  totals: {
    events: number
    sessions: number
    views: number
    outbound: number
    dwell_secs: number
    median_session_secs: number
    median_views_per_session: number
    scored_items: number
  }
  items: Record<string, EngagementItem>
  /** url → [[다음에 본 url, 횟수], ...] */
  next: Record<string, [string, number][]>
}

let cached: Promise<EngagementDoc | null> | null = null

function load(): Promise<EngagementDoc | null> {
  if (cached) return cached
  cached = fetch('/engagement.json')
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<EngagementDoc>
    })
    .catch(() => null)
  return cached
}

export interface EngagementState {
  doc: EngagementDoc | null
  /** 0~1. 기록이 없으면 0 — 순위를 흔들지 않는다. */
  score: (url: string) => number
  /** 이 항목 다음에 실제로 많이 본 것들. 기록이 없으면 빈 배열. */
  next: (url: string) => string[]
}

const NONE: string[] = []

export function useEngagement(): EngagementState {
  const [doc, setDoc] = useState<EngagementDoc | null>(null)
  useEffect(() => {
    let cancelled = false
    load().then((d) => !cancelled && setDoc(d))
    return () => {
      cancelled = true
    }
  }, [])

  return {
    doc,
    score: (url) => doc?.items?.[url]?.score ?? 0,
    next: (url) => doc?.next?.[url]?.map(([u]) => u) ?? NONE,
  }
}

/**
 * 유사도 순서에 행동 점수를 섞는다.
 *
 * 유사도를 갈아엎지 않고 **밀어 올리기만** 한다(가중치 BOOST). 행동 기록은 초반에
 * 표본이 적어 몇 사람의 클릭이 전체를 좌우할 수 있는데, 그걸 그대로 믿으면 처음
 * 눌린 몇 개만 계속 위에 남는 굳은 추천이 된다. 유사도가 바닥을 잡고 행동이
 * 순위를 조금 흔드는 정도가 맞다.
 *
 * '그다음에 실제로 본 것'은 더 직접적인 근거라 따로 더 얹는다.
 */
const BOOST = 0.35
const NEXT_BONUS = 0.25

export function blendByEngagement<T extends { url: string; score: number }>(
  items: T[],
  eng: EngagementState,
  sourceUrl: string,
): T[] {
  if (!eng.doc) return items
  const nextSet = new Set(eng.next(sourceUrl))
  return [...items].sort((a, b) => {
    const av = a.score + BOOST * eng.score(a.url) + (nextSet.has(a.url) ? NEXT_BONUS : 0)
    const bv = b.score + BOOST * eng.score(b.url) + (nextSet.has(b.url) ? NEXT_BONUS : 0)
    return bv - av
  })
}
