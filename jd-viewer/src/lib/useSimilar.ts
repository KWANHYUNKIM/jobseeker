import { useEffect, useState } from 'react'

/** similar_jobs.json / similar_posts.json 의 형식 (semantic/similar.py 가 생성). */
interface SimilarFile {
  generated_at: string
  kind: string
  top_k: number
  docs: Record<string, { u: string; c: string; t: string }> // 문서 id → url / 회사 / 제목
  similar: Record<string, [string, number][]> // 문서 id → [[대상 id, 점수], ...]
}

export interface SimilarItem {
  url: string
  company: string
  title: string
  score: number
}

interface State {
  /** url 로 유사 문서를 찾는다. 데이터가 없으면 빈 배열. */
  lookup: (url: string) => SimilarItem[]
  loading: boolean
  /** 아직 파이프라인을 돌리지 않아 파일이 없는 경우도 포함 — UI 는 조용히 숨긴다. */
  error: string | null
}

const EMPTY: SimilarItem[] = []

interface Index {
  byUrl: Map<string, string> // url → 문서 id
  file: SimilarFile
}

// 모달을 열 때마다 수 MB 를 다시 받지 않도록 모듈 스코프에 promise 를 캐시한다.
const cache = new Map<string, Promise<Index | null>>()

function load(path: string): Promise<Index | null> {
  const hit = cache.get(path)
  if (hit) return hit
  const p = fetch(path)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json() as Promise<SimilarFile>
    })
    .then((file) => {
      const byUrl = new Map<string, string>()
      for (const [id, d] of Object.entries(file.docs || {})) byUrl.set(d.u, id)
      return { byUrl, file }
    })
    .catch(() => null) // 파일이 없으면(파이프라인 미실행) 추천을 그냥 감춘다
  cache.set(path, p)
  return p
}

function useSimilar(path: string): State {
  const [index, setIndex] = useState<Index | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    load(path).then((idx) => {
      if (cancelled) return
      setIndex(idx)
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [path])

  const lookup = (url: string): SimilarItem[] => {
    if (!index || !url) return EMPTY
    const id = index.byUrl.get(url)
    if (!id) return EMPTY
    const pairs = index.file.similar[id]
    if (!pairs) return EMPTY
    const out: SimilarItem[] = []
    for (const [targetId, score] of pairs) {
      const doc = index.file.docs[targetId]
      if (doc) out.push({ url: doc.u, company: doc.c, title: doc.t, score })
    }
    return out
  }

  return { lookup, loading, error: index ? null : loading ? null : '추천 데이터 없음' }
}

export function useSimilarJobs(): State {
  return useSimilar('/similar_jobs.json')
}

export function useSimilarPosts(): State {
  return useSimilar('/similar_posts.json')
}
