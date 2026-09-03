import { useEffect, useRef } from 'react'

/**
 * 행동 기록. 무엇을 눌렀고 어디에 얼마나 머물렀는지를 남긴다.
 *
 * **왜 필요한가.** 지금 추천('비슷한 공고')은 임베딩 유사도만 본다. 그건 "내용이
 * 닮았다"는 뜻이지 "사람들이 실제로 그다음에 본다"는 뜻이 아니다. 둘을 섞으려면
 * 뒤쪽 근거가 있어야 하는데, 지금까지 아무것도 쌓지 않았다. 여기서부터 쌓는다.
 *
 * **개인을 식별하지 않는다.** 세션 id 는 브라우저에서 만든 난수이고 서버로 가는
 * 것은 그 난수와 '무엇을 눌렀나'뿐이다. 이름·이메일·IP 를 붙이지 않는다. 사람을
 * 알아내려는 게 아니라 어떤 공고가 다음 공고를 부르는지를 알려는 것이기 때문이다.
 *
 * **없어도 사이트는 그대로 돈다.** 수집 서버가 안 떠 있으면 한 번 실패하고 조용히
 * 꺼진다(검색 API 가 없을 때 의미 검색 UI 를 감추는 것과 같은 규칙). 통계 때문에
 * 화면이 멈추는 일은 없어야 한다.
 */

const ENDPOINT = '/collect'
const SID_KEY = 'jd.sid'
const FLUSH_MS = 10_000
const MAX_QUEUE = 40

export interface TrackEvent {
  /** 'view' | 'click' | 'dwell' 등. 서버는 무엇이 오든 그대로 받아 적는다. */
  t: string
  /** 무엇에 대한 사건인가. 공고는 url, 글은 url, 필터는 '축:값'. */
  k?: string
  /** 어디서 눌렀나. 같은 공고라도 목록에서 왔는지 추천에서 왔는지가 핵심이다. */
  from?: string
  /** 머문 초. dwell 에만 있다. */
  s?: number
  ts: number
}

let sid = ''
let queue: TrackEvent[] = []
let timer: ReturnType<typeof setInterval> | null = null
let disabled = false

function sessionId(): string {
  if (sid) return sid
  try {
    const got = localStorage.getItem(SID_KEY)
    if (got) return (sid = got)
    // 난수 12자. 사람을 가리키는 게 아니라 '한 번의 방문 흐름'을 잇는 실이다.
    const made = Math.random().toString(36).slice(2, 8) + Date.now().toString(36).slice(-6)
    localStorage.setItem(SID_KEY, made)
    return (sid = made)
  } catch {
    // 저장소가 막힌 브라우저. 이번 탭 동안만 유지되는 id 로 떨어진다.
    return (sid = 'tmp' + Math.random().toString(36).slice(2, 10))
  }
}

function send(events: TrackEvent[], beacon: boolean): void {
  if (!events.length || disabled) return
  const body = JSON.stringify({ sid: sessionId(), events })
  try {
    if (beacon && navigator.sendBeacon) {
      // 페이지를 떠나는 중에도 도착한다. fetch 는 이 시점에 취소된다.
      navigator.sendBeacon(ENDPOINT, new Blob([body], { type: 'application/json' }))
      return
    }
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
    }).catch(() => {
      // 수집 서버가 없는 배포다. 매 요청 실패로 콘솔을 더럽히지 않도록 꺼 버린다.
      disabled = true
    })
  } catch {
    disabled = true
  }
}

function flush(beacon = false): void {
  if (!queue.length) return
  const batch = queue
  queue = []
  send(batch, beacon)
}

function ensureTimer(): void {
  if (timer || typeof window === 'undefined') return
  timer = setInterval(() => flush(false), FLUSH_MS)
  // 탭을 닫거나 뒤로 갈 때가 마지막 기회다. visibilitychange 까지 같이 보는 이유는
  // 모바일 사파리가 pagehide 를 건너뛰고 백그라운드로 보내는 경우가 있어서다.
  window.addEventListener('pagehide', () => flush(true))
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush(true)
  })
}

export function track(t: string, k?: string, from?: string, s?: number): void {
  if (disabled || typeof window === 'undefined') return
  ensureTimer()
  queue.push({ t, k, from, s, ts: Date.now() })
  if (queue.length >= MAX_QUEUE) flush(false)
}

/**
 * 어디서 왔나. 호스트 이름까지만 본다.
 *
 * 전체 referrer URL 에는 검색어나 사설 페이지 경로가 붙어 오는 일이 있어서 그대로
 * 적으면 남의 사정을 우리 로그에 옮겨 적는 셈이 된다. 유입 경로를 알기에는
 * '어느 사이트에서 왔나'로 충분하다.
 */
function referrerSource(): string {
  const r = document.referrer
  if (!r) return 'direct'
  try {
    const h = new URL(r).hostname.replace(/^www\./, '')
    // 같은 사이트에서 온 것은 유입이 아니라 사이트 안에서의 이동이다.
    return h === location.hostname ? 'internal' : h.slice(0, 60)
  } catch {
    return 'unknown'
  }
}

/**
 * 방문 시작. 페이지가 실제로 로드될 때 한 번만 부른다.
 *
 * SPA 라 화면 이동은 대부분 로드를 다시 하지 않는다. 그래서 이 사건은 '새 방문'과
 * 거의 같은 뜻이 된다 — 몇 명이 들어왔고 어디서 왔는지를 세는 재료다.
 * 주소는 경로만 남긴다(쿼리·해시 제외) — 검색어나 토큰이 붙어 있을 수 있다.
 */
export function trackVisit(): void {
  track('session', location.pathname.slice(0, 200), referrerSource())
}

/**
 * 항목 하나에 머문 시간.
 *
 * 탭이 숨겨진 동안은 세지 않는다. 창을 띄워 두고 자리를 뜬 시간까지 '봤다'로 세면
 * 체류시간은 늘 부풀고, 그 숫자로 추천을 고치면 엉뚱한 것이 위로 올라온다.
 * 1초 미만은 버린다 — 스쳐 지나간 것이다.
 */
export function useDwell(key: string | null | undefined, from?: string): void {
  const startedAt = useRef<number | null>(null)
  const acc = useRef(0)

  useEffect(() => {
    if (!key) return
    acc.current = 0
    startedAt.current = document.visibilityState === 'visible' ? Date.now() : null

    const pause = () => {
      if (startedAt.current !== null) {
        acc.current += Date.now() - startedAt.current
        startedAt.current = null
      }
    }
    const resume = () => {
      if (startedAt.current === null) startedAt.current = Date.now()
    }
    const onVis = () => (document.visibilityState === 'visible' ? resume() : pause())

    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('pagehide', pause)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('pagehide', pause)
      pause()
      const secs = Math.round(acc.current / 1000)
      if (secs >= 1) track('dwell', key, from, secs)
    }
  }, [key, from])
}
