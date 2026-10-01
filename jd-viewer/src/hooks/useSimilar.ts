import { useEffect, useState } from 'react'
import { apiGet, getJson } from '../api/client'

/**
 * 비슷한 공고·관련 글. 공고 상세와 글 상세가 같이 쓴다.
 *
 * 뷰어 API(`/api/similar`)가 먼저다 — 파이프라인이 굳혀 둔 top-K 중 **지금 모집중인
 * 공고만** 돌려준다. API 가 없는 배포에서는 예전처럼 similar_*.json(4MB)을 받아 url 로 찾는다.
 */

export interface SimilarItem {
  url: string
  company: string
  title: string
  score: number
}

type Kind = 'job' | 'post'

/** similar_jobs.json / similar_posts.json 의 형식 (파이프라인 semantic·vectors 의 similar 가 생성). */
interface SimilarFile {
  generated_at: string
  kind: string
  top_k: number
  docs: Record<string, { u: string; c: string; t: string }> // 문서 id → url / 회사 / 제목
  similar: Record<string, [string, number][]> // 문서 id → [[대상 id, 점수], ...]
}

const FILE: Record<Kind, string> = { job: '/similar_jobs.json', post: '/similar_posts.json' }

// 모달을 열 때마다 수 MB 를 다시 받지 않도록 모듈 스코프에 promise 를 캐시한다.
const fileCache = new Map<Kind, Promise<((url: string) => SimilarItem[]) | null>>()

function fileLookup(kind: Kind) {
  let p = fileCache.get(kind)
  if (!p) {
    p = getJson<SimilarFile>(FILE[kind])
      .then((file) => {
        const byUrl = new Map<string, string>()
        for (const [id, d] of Object.entries(file.docs || {})) byUrl.set(d.u, id)
        return (url: string) => {
          const id = byUrl.get(url)
          const pairs = id ? file.similar[id] : undefined
          const out: SimilarItem[] = []
          for (const [targetId, score] of pairs ?? []) {
            const doc = file.docs[targetId]
            if (doc) out.push({ url: doc.u, company: doc.c, title: doc.t, score })
          }
          return out
        }
      })
      .catch(() => null) // 파일이 없으면(파이프라인 미실행) 추천을 그냥 감춘다
    fileCache.set(kind, p)
  }
  return p
}

async function fetchSimilar(kind: Kind, url: string, signal: AbortSignal): Promise<SimilarItem[]> {
  try {
    const q = new URLSearchParams({ url, kind })
    return (await apiGet<{ items: SimilarItem[] }>(`/api/similar?${q}`, { signal })).items
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    const lookup = await fileLookup(kind)
    return lookup ? lookup(url) : []
  }
}

interface State {
  items: SimilarItem[]
  loading: boolean
}

const EMPTY: SimilarItem[] = []

function useSimilar(kind: Kind, url: string | null): State {
  const [done, setDone] = useState<{ url: string; items: SimilarItem[] } | null>(null)
  useEffect(() => {
    if (!url) return
    const ac = new AbortController()
    fetchSimilar(kind, url, ac.signal)
      .then((items) => setDone({ url, items }))
      .catch((e) => {
        if (e.name !== 'AbortError') setDone({ url, items: EMPTY })
      })
    return () => ac.abort()
  }, [kind, url])
  if (!url) return { items: EMPTY, loading: false }
  const fresh = done?.url === url
  return { items: fresh ? done.items : EMPTY, loading: !fresh }
}

export function useSimilarJobs(url: string | null): State {
  return useSimilar('job', url)
}

export function useSimilarPosts(url: string | null): State {
  return useSimilar('post', url)
}
