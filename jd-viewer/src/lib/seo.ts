import { useEffect } from 'react'

// 화면마다 <head> 를 갈아끼운다 — 제목·설명·정규 URL·오픈그래프·구조화 데이터.
//
// SPA 는 문서가 하나뿐이라 무엇을 하지 않으면 모든 주소가 같은 제목·같은 설명으로
// 색인된다. 검색 결과에서 공고 1만 건이 전부 "JD Viewer" 한 줄로 보이는 상태.
// 그래서 라우트가 바뀔 때마다 여기서 태그를 다시 쓴다.
//
// 빌드 때 scripts/prerender.mjs 가 같은 내용을 정적 HTML 에 미리 박아 둔다.
// (자바스크립트를 실행하지 않는 크롤러·미리보기 봇이 보는 건 그쪽이다.)
// 두 곳의 문구 규칙이 어긋나면 프리렌더와 실제 화면의 메타가 달라지므로,
// 제목/설명 문구를 고칠 땐 반드시 양쪽을 같이 고친다.

export const SITE_NAME = 'JD Viewer'
export const SITE_DESC =
  '국내외 개발자 채용공고를 한곳에 모아 기술스택·기업·트렌드로 분석하는 채용 정보 뷰어'

/** 정규 URL 의 기준 오리진. 배포 도메인이 바뀌면 .env 의 VITE_SITE_URL 만 고친다. */
export const SITE_URL: string =
  (import.meta.env.VITE_SITE_URL as string | undefined)?.replace(/\/$/, '') ||
  (typeof window !== 'undefined' ? window.location.origin : '')

export function absUrl(path: string): string {
  return `${SITE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

/** 설명문은 한 줄로 눌러 담는다 — 줄바꿈·중복 공백이 있으면 검색결과 스니펫이 지저분해진다. */
export function clip(text: string | undefined | null, max = 155): string {
  if (!text) return ''
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length <= max ? flat : `${flat.slice(0, max - 1).trimEnd()}…`
}

export interface Seo {
  title: string
  description?: string
  /** 경로(`/jobs/wanted-1`) 또는 절대 URL */
  canonical?: string
  /** 색인시키면 안 되는 화면(검색 결과 등)은 'noindex, follow' */
  robots?: string
  /** schema.org 구조화 데이터 (JobPosting 등) */
  jsonLd?: object | null
}

const MANAGED = 'data-seo' // 이 훅이 만든 태그만 지우기 위한 표식

function setMeta(attr: 'name' | 'property', key: string, content: string) {
  if (!content) return
  const el = document.createElement('meta')
  el.setAttribute(attr, key)
  el.setAttribute('content', content)
  el.setAttribute(MANAGED, '')
  document.head.appendChild(el)
}

/**
 * head 를 이 화면의 것으로 갈아끼운다.
 *
 * null 을 주면 아무것도 하지 않는다 — "이 주소의 메타는 다른 컴포넌트가 책임진다"는 뜻이다.
 * 회사·레이더·역설계 상세처럼 제목에 들어갈 데이터를 App 이 안 들고 있는 화면에서,
 * App 이 탭 제목으로 덮어써 버리는 걸 막는다(그 사이에는 프리렌더된 제목이 그대로 남는다).
 */
export function useSeo(seo: Seo | null): void {
  const { title, description, canonical, robots, jsonLd } = seo ?? ({} as Partial<Seo>)
  const jsonLdKey = jsonLd ? JSON.stringify(jsonLd) : ''

  useEffect(() => {
    if (!title) return
    // 이전 라우트가 남긴 태그를 먼저 걷어낸다(정적 HTML 이 심어 둔 것도 표식이 같다).
    for (const el of document.querySelectorAll(`[${MANAGED}]`)) el.remove()

    const full = title === SITE_NAME ? title : `${title} | ${SITE_NAME}`
    document.title = full
    const desc = clip(description || SITE_DESC)
    const url = canonical
      ? canonical.startsWith('http')
        ? canonical
        : absUrl(canonical)
      : absUrl(window.location.pathname)

    const link = document.createElement('link')
    link.rel = 'canonical'
    link.href = url
    link.setAttribute(MANAGED, '')
    document.head.appendChild(link)

    setMeta('name', 'description', desc)
    if (robots) setMeta('name', 'robots', robots)
    setMeta('property', 'og:type', 'website')
    setMeta('property', 'og:site_name', SITE_NAME)
    setMeta('property', 'og:title', full)
    setMeta('property', 'og:description', desc)
    setMeta('property', 'og:url', url)
    setMeta('property', 'og:locale', 'ko_KR')
    setMeta('name', 'twitter:card', 'summary')
    setMeta('name', 'twitter:title', full)
    setMeta('name', 'twitter:description', desc)

    if (jsonLdKey) {
      const s = document.createElement('script')
      s.type = 'application/ld+json'
      s.textContent = jsonLdKey
      s.setAttribute(MANAGED, '')
      document.head.appendChild(s)
    }
  }, [title, description, canonical, robots, jsonLdKey])
}
