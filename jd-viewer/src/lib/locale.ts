import { useSyncExternalStore } from 'react'

/**
 * 보는 사람의 언어.
 *
 * **왜 IP 가 아니라 브라우저 언어인가.** "외국에서 보면 외국어로"의 실제 구현은
 * 위치가 아니라 `navigator.languages` 다. 위치와 읽는 말은 다른 문제라서 —
 * 출장 중인 한국인, 서울에 사는 외국인, VPN 을 쓰는 사람 모두 위치로는 틀린다.
 * 브라우저 언어는 사용자가 자기 기기에 직접 설정해 둔 값이라 훨씬 정확하다.
 *
 * **고르면 기억한다.** 자동 감지는 첫 방문에만 쓴다. 한 번이라도 직접 바꾸면
 * 그 뒤로는 그 선택이 이긴다 — 감지가 틀렸을 때 매번 다시 바꾸게 하면 안 된다.
 *
 * 지금 이 값이 바꾸는 것은 기술 블로그 본문(원문/번역)과 `<html lang>` 이다.
 * 인터페이스 문구와 공고 본문 번역은 아직 한국어뿐이라 여기에 걸릴 것이 없다.
 * 그 둘이 준비되면 읽는 쪽만 늘리면 되도록 저장소를 여기 하나로 모아 둔다.
 */
export type Locale = 'ko' | 'en'

const KEY = 'jd.locale'

function fromStorage(): Locale | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'ko' || v === 'en' ? v : null
  } catch {
    return null // 시크릿 창·저장소 차단. 감지로 떨어지면 된다.
  }
}

/** 브라우저가 선호한다고 말한 언어 목록에서 첫 판단. ko 계열이 아니면 en 으로 본다. */
export function detectLocale(): Locale {
  const tags =
    typeof navigator === 'undefined'
      ? []
      : navigator.languages?.length
        ? navigator.languages
        : [navigator.language]
  for (const tag of tags) {
    if (!tag) continue
    if (tag.toLowerCase().startsWith('ko')) return 'ko'
    return 'en' // 첫 번째로 알아들은 태그가 한국어가 아니면 거기서 끝낸다
  }
  return 'ko'
}

let current: Locale = fromStorage() ?? detectLocale()

if (typeof document !== 'undefined') {
  document.documentElement.lang = current
}

const listeners = new Set<() => void>()

function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getLocale(): Locale {
  return current
}

export function setLocale(next: Locale): void {
  if (next === current) return
  current = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    /* 저장 못 해도 이번 세션 동안은 바뀐 채로 쓴다 */
  }
  if (typeof document !== 'undefined') document.documentElement.lang = next
  listeners.forEach((fn) => fn())
}

export function useLocale(): Locale {
  // 프리렌더(서버) 스냅샷은 감지 없이 ko 다. index.html 이 lang="ko" 로 나가고
  // 지금 공고·문구가 전부 한국어라 그게 사실에 맞다. 브라우저에서 마운트되면
  // 감지·저장값으로 바뀐다.
  return useSyncExternalStore(subscribe, getLocale, () => 'ko' as Locale)
}
