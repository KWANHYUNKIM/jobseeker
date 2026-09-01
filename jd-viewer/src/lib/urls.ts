import type { Job } from '../types'
import { clip, SITE_DESC, SITE_NAME } from './seo'

// 주소 규칙을 한곳에 모은다. 빌드 때 scripts/prerender.mjs 가 같은 규칙으로
// 정적 HTML 과 sitemap.xml 을 찍으므로, 여기를 고치면 그쪽도 같이 고쳐야 한다.

/** 공고 하나를 가리키는 안정적인 키. 사이트 + 사이트 내 공고 번호. */
export function jobKey(j: Pick<Job, 'site' | 'pid'>): string {
  return `${j.site}-${j.pid}`
}

export const paths = {
  jobs: () => '/',
  job: (j: Pick<Job, 'site' | 'pid'>) => `/jobs/${jobKey(j)}`,
  companies: () => '/companies',
  company: (norm: string) => `/companies/${encodeURIComponent(norm)}`,
  mindmap: () => '/mindmap',
  blog: () => '/blog',
  blogPost: (id: string) => `/blog/${encodeURIComponent(id)}`,
  radar: () => '/radar',
  radarCompany: (key: string) => `/radar/${encodeURIComponent(key)}`,
  calendar: () => '/calendar',
  reposts: () => '/reposts',
  trend: (tech?: string) => (tech ? `/trend?tech=${encodeURIComponent(tech)}` : '/trend'),
  reveng: () => '/reveng',
  revengCompany: (slug: string) => `/reveng/${encodeURIComponent(slug)}`,
  revengDoc: (slug: string) => `/reveng/문서/${encodeURIComponent(slug)}`,
}

/** 블로그 글의 주소 키 — 본문 id 가 있으면 그걸, 없으면 원문 URL 로 만든 짧은 해시. */
export function blogKey(p: { content_id?: string; url: string }): string {
  if (p.content_id) return p.content_id
  let h = 0
  for (let i = 0; i < p.url.length; i++) h = (h * 31 + p.url.charCodeAt(i)) | 0
  return `u${(h >>> 0).toString(36)}`
}

// ── 화면별 제목·설명 ────────────────────────────────────────────────────
// 검색결과에 그대로 뜨는 문장이다. 회사·직무·기술처럼 사람들이 실제로 검색하는
// 단어가 앞에 오도록 쓴다("JD Viewer - 페이지" 같은 제목은 아무도 검색하지 않는다).

export const TAB_SEO: Record<string, { title: string; desc: string }> = {
  jobs: {
    title: '개발자 채용공고 모아보기',
    desc: `원티드·점핏·잡코리아·사람인·데보션과 해외 원격 보드의 개발자 채용공고를 한곳에서 기술스택·경력·직무로 걸러 봅니다. ${SITE_NAME}`,
  },
  companies: {
    title: '기업 기술스택 분석',
    desc: '채용공고에서 뽑아낸 회사별 기술스택·도메인·아키텍처 분석. 어떤 회사가 무엇으로 개발하는지 공고 데이터로 확인합니다.',
  },
  mindmap: {
    title: '개발자 커리어 마인드맵',
    desc: '직무·기술·경력 단계를 하나의 지도로 이은 개발자 커리어 마인드맵.',
  },
  blog: {
    title: '기업 기술블로그 모아보기',
    desc: '국내외 기업 기술블로그 글을 기술스택·카테고리로 모으고 한국어 요약과 번역을 붙였습니다.',
  },
  radar: {
    title: '글로벌 IT 기업 100곳 기술 레이더',
    desc: '글로벌 IT 기업 100곳의 언어·기술스택·아키텍처·채용 전형을 정리한 기술 레이더.',
  },
  calendar: {
    title: '개발자 채용 모집 캘린더',
    desc: '공고 마감일과 모집 시작일을 달력으로. 언제 열리고 언제 닫히는지 한눈에 봅니다.',
  },
  reposts: {
    title: '재공고 추적',
    desc: '같은 포지션이 반복해서 다시 올라오는 공고를 추적합니다. 자주 다시 뜨는 자리가 보입니다.',
  },
  trend: {
    title: '개발 기술 트렌드',
    desc: '채용공고에서 언급된 기술의 비중 변화로 보는 개발 기술 트렌드와 학습 경로.',
  },
  reveng: {
    title: '기업 기술 역설계',
    desc: '공개 자료만으로 재구성한 기업의 비즈니스 모델 → 도메인 → 기능 구현 → 시스템 연결.',
  },
}

export function jobTitle(j: Job): string {
  return `${j.company} ${j.title}`
}

export function jobDescription(j: Job): string {
  const stack = (j.tech_stack || []).slice(0, 6).join(', ')
  const head = [j.company, j.career, j.location].filter(Boolean).join(' · ')
  const body = j.main_tasks || j.qualifications || j.full_jd || SITE_DESC
  return clip(`${head}${stack ? ` · ${stack}` : ''} — ${body}`)
}

/**
 * schema.org JobPosting. 구글 채용 검색이 읽는 형식.
 * datePosted 는 원본 사이트가 안 주는 공고가 대부분이라 넣지 않는다(없는 날짜를
 * 지어내면 그게 곧 잘못된 구조화 데이터다). 마감일은 ISO 로 확인될 때만 넣는다.
 */
export function jobJsonLd(j: Job, url: string): object {
  const iso = j.deadline_date && /^\d{4}-\d{2}-\d{2}/.test(j.deadline_date) ? j.deadline_date : null
  return {
    '@context': 'https://schema.org',
    '@type': 'JobPosting',
    title: j.title,
    description: clip([j.main_tasks, j.qualifications, j.preferences].filter(Boolean).join('\n'), 4000),
    identifier: { '@type': 'PropertyValue', name: j.site, value: j.pid },
    hiringOrganization: { '@type': 'Organization', name: j.company },
    ...(j.location
      ? { jobLocation: { '@type': 'Place', address: { '@type': 'PostalAddress', addressLocality: j.location, addressCountry: j.overseas ? undefined : 'KR' } } }
      : j.overseas
        ? { jobLocationType: 'TELECOMMUTE' }
        : {}),
    ...(iso ? { validThrough: iso } : {}),
    ...(j.tech_stack?.length ? { skills: j.tech_stack.join(', ') } : {}),
    ...(j.career ? { experienceRequirements: j.career } : {}),
    url,
    sameAs: j.url,
    directApply: false,
  }
}

export function breadcrumbJsonLd(items: { name: string; url: string }[]): object {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: it.url,
    })),
  }
}
