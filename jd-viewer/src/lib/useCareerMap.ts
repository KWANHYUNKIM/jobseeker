import { useEffect, useState } from 'react'

// public/career_map.json — bin/build_career_map.py 가 생성.
// JD 임베딩(bge-m3)을 군집화한 결과이므로 라벨은 사람이 정한 직군명이 아니라
// 군집에서 변별력(lift) 순으로 뽑아낸 단어들이다.

export interface CareerTerm {
  name: string
  n: number
  share: number // 군집 내 등장 비율(%)
  lift: number // 전체 대비 과대표집 배수
}

export interface CareerGap {
  name: string
  to_share: number // 목표 군집에서의 점유율(%)
  from_share: number // 출발 군집에서의 점유율(%)
  gap: number // to - from (%p) — 이동에 드는 학습 비용
}

export interface CareerEdge {
  to: number
  to_label: string
  similarity: number // 군집 중심 간 코사인
  gap: CareerGap[]
  shared: string[]
}

export interface CareerCluster {
  id: number
  label: string
  size: number
  share: number
  terms: CareerTerm[]
  tech: CareerTerm[]
  companies: { name: string; n: number }[]
  bands: { name: string; n: number }[]
  samples: { title: string; company: string; url: string; site: string }[]
  cohesion: number // 중심과의 평균 코사인 — 낮으면 그 군집은 느슨하다
  neighbors: CareerEdge[]
}

export interface CareerMapFile {
  generated_at: string
  source: string
  jobs: number
  k: number
  seed: number
  clusters: CareerCluster[]
}

export function useCareerMap() {
  const [data, setData] = useState<CareerMapFile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/career_map.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status} - career_map.json`)
        return r.json()
      })
      .then((d: CareerMapFile) => {
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
