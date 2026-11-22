import { describe, expect, it } from 'vitest'
import { firstReads, roadmapRank } from './roadmap'
import type { LectureCard, Track } from '../hooks/useLectures'

const card = (id: string, series: string, no: number, level: LectureCard['level']): LectureCard =>
  ({ id, series, no, level, title: id, title_ko: id, topic: 'ml-basics', tags: [], one_line: '', url: '', platform: 'youtube', chapters: 1, written_at: '' }) as LectureCard

const track: Track = {
  key: 'ai', label: 'AI', for: '', goal: '', how: [], done: 0, total: 0,
  steps: [
    { title: '1단계', level: '입문', why: '', series: [{ key: 'easy', title: '', done: 0, total: 0 }], done: 0, total: 0 },
    { title: '2단계', level: '중급', why: '', series: [{ key: 'hard', title: '', done: 0, total: 0 }], done: 0, total: 0 },
  ],
}

describe('roadmap', () => {
  it('트랙 안에서는 단계 → 강의 차례로 줄 세운다', () => {
    const rank = roadmapRank(track)
    const xs = [card('h1', 'hard', 1, '입문'), card('e2', 'easy', 2, '중급'), card('e1', 'easy', 1, '입문'), card('x', 'other', 1, '입문')]
    expect(xs.sort((a, b) => rank(a) - rank(b)).map((c) => c.id)).toEqual(['e1', 'e2', 'h1', 'x'])
  })
  it('먼저 볼 노트는 쉬운 것부터', () => {
    const xs = [card('a3', 'easy', 3, '입문'), card('a1', 'easy', 1, '심화'), card('a2', 'easy', 2, '입문')]
    expect(firstReads(xs, ['easy'], 2).map((c) => c.id)).toEqual(['a2', 'a3'])
  })
})
