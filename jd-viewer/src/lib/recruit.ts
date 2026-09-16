import type { Job } from '../types'

/**
 * 공고의 모집 상태를 **한 조각의 화면 정보**로 정리한다.
 *
 * 지금까지 목록은 `status` 두 값만 보고 '마감' 배지를 붙일지 말지를 정했다.
 * 그런데 `active` 안에 서로 다른 세 가지가 섞여 있다:
 *
 *   ① 마감일을 알고, 그 날이 아직 안 왔다        → 언제까지인지 보여줄 수 있다
 *   ② 상시채용이라 마감일이 없다                 → 그것도 정보다
 *   ③ **마감일을 알 방법이 없어 열어 둔 것**      → 열려 있다는 근거가 없다
 *
 * ③ 이 모집중의 절반을 넘는다(원본에 마감 표기가 없는 wanted, 아직 재확인이
 * 닿지 않은 공고). 셋을 같은 얼굴로 보여주면 두 달 전에 끝난 자리를 오늘 열린
 * 자리와 나란히 놓게 된다. 근거(`status_source`)를 배지로 드러낸다.
 */
export type RecruitTone = 'closed' | 'urgent' | 'open' | 'always' | 'unverified'

export interface RecruitBadge {
  label: string
  title: string
  tone: RecruitTone
}

/** 오늘 00:00 기준 남은 일수. 날짜만 비교한다(시:분은 애초에 없다). */
export function daysUntil(iso: string | undefined, today = new Date()): number | null {
  if (!iso) return null
  const d = new Date(iso + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return null
  const base = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((d.getTime() - base.getTime()) / 86400000)
}

export function recruitBadge(j: Job, today = new Date()): RecruitBadge | null {
  if (j.status === 'closed') {
    return { label: '마감', title: j.closed_reason || '마감', tone: 'closed' }
  }
  const left = daysUntil(j.deadline_date, today)
  if (left !== null && left < 0) {
    // export 는 status 를 읽는 시점에 계산하므로 여기 걸릴 일이 거의 없다. 다만
    // 파일이 묵었거나 export 와 지금 사이에 자정이 지나면 생긴다. 그때 '모집중'
    // 으로 보여주는 것보다는 지난 마감이라고 말하는 쪽이 맞다.
    return { label: '마감', title: `마감일이 지났습니다 (${j.deadline_date})`, tone: 'closed' }
  }
  if (left !== null) {
    return {
      label: left === 0 ? '오늘 마감' : `D-${left}`,
      title: `마감 ${j.deadline_date}`,
      tone: left <= 3 ? 'urgent' : 'open',
    }
  }
  if (j.status_source === 'always_open') {
    return { label: '상시', title: '상시/수시 채용 — 마감일이 없습니다', tone: 'always' }
  }
  if (j.status_source === 'unknown') {
    return {
      label: '미확인',
      title: '원본에 마감 표기가 없어 열어 둔 공고입니다. 지원 전에 원본을 확인하세요',
      tone: 'unverified',
    }
  }
  return null
}

/** 등록일(원본이 말한 값) 또는 처음 본 날(추정). 없으면 null. */
export function postedOf(j: Job): { iso: string; estimated: boolean } | null {
  if (j.posted_date) return { iso: j.posted_date, estimated: false }
  if (j.first_seen_at) return { iso: j.first_seen_at, estimated: true }
  return null
}

/**
 * '오늘' / '3일 전' / '2026-06-11'. 오래된 것은 날짜 그대로 적는다 —
 * "97일 전" 은 세어 보기 전에는 언제인지 알 수 없다.
 */
export function postedText(iso: string, today = new Date()): string {
  const ago = -(daysUntil(iso, today) ?? 0)
  if (ago < 0) return iso
  if (ago === 0) return '오늘'
  if (ago === 1) return '어제'
  if (ago <= 30) return `${ago}일 전`
  return iso
}
