import type { LectureCard, Track } from '../hooks/useLectures'

// 로드맵 순서 계산 — 화면(TrackRoadmap·LecturesView)과 테스트가 같이 쓴다.

const LEVEL_RANK: Record<string, number> = { 입문: 0, 중급: 1, 심화: 2 }

/** 단계의 과목들에서 먼저 볼 노트 — 쉬운 것 먼저, 같으면 1강부터. */
export function firstReads(items: LectureCard[], seriesKeys: string[], n = 3): LectureCard[] {
  const order = new Map(seriesKeys.map((k, i) => [k, i]))
  return items
    .filter((c) => c.series && order.has(c.series))
    .sort(
      (a, b) =>
        (LEVEL_RANK[a.level] ?? 9) - (LEVEL_RANK[b.level] ?? 9) ||
        (order.get(a.series!) ?? 0) - (order.get(b.series!) ?? 0) ||
        (a.no ?? 0) - (b.no ?? 0),
    )
    .slice(0, n)
}

/** 트랙 안에서의 자리 — 로드맵 단계 → 단계 안 과목 → 강의 차례. 로드맵 밖 노트는 맨 뒤. */
export function roadmapRank(t: Track | undefined): (c: LectureCard) => number {
  const pos = new Map<string, number>()
  t?.steps.forEach((st, i) => st.series.forEach((s, j) => pos.set(s.key, i * 100 + j)))
  return (c) => (c.series && pos.has(c.series) ? (pos.get(c.series) as number) * 1000 + (c.no ?? 0) : 1e9)
}
