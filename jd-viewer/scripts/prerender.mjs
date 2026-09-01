#!/usr/bin/env node
/**
 * 빌드 후 주소별 정적 HTML + sitemap.xml + robots.txt 를 찍는다.
 *
 * 왜 필요한가
 *  SPA 는 서버가 어떤 주소로 요청받든 같은 index.html 한 장을 돌려준다. 크롤러가
 *  자바스크립트를 실행해 주기도 하지만, (1) 실행은 늦고 예산이 있고, (2) 카카오톡·
 *  슬랙·X 같은 미리보기 봇은 아예 실행하지 않는다. 그래서 공고·회사처럼 "이건 한 장의
 *  문서다" 싶은 주소는 제목·설명·본문 요약·구조화 데이터를 미리 박아 둔 HTML 을 깐다.
 *  브라우저로 들어오면 그 HTML 위에서 React 가 마운트하며 평소 화면으로 바뀐다.
 *
 * 문구 규칙은 src/lib/urls.ts, 태그 조립 규칙은 src/lib/seo.ts 와 짝이다. 한쪽만
 * 고치면 크롤러가 보는 메타와 사람이 보는 메타가 갈라진다.
 *
 * 실행: node scripts/prerender.mjs   (npm run build 끝에 자동 실행)
 * 환경변수:
 *   SITE_URL        정규 URL 의 기준 오리진
 *   PRERENDER_JOBS  공고 페이지 최대 개수(기본: 전부). 디스크를 아끼고 싶을 때만.
 */
import { mkdirSync, readFileSync, writeFileSync, statSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(ROOT, 'dist')
const PUBLIC = join(ROOT, 'public')

const SITE_URL = (process.env.SITE_URL || 'https://prevail-chapter-uncorrupt.ngrok-free.dev').replace(/\/$/, '')
const SITE_NAME = 'JD Viewer'
const JOB_LIMIT = Number(process.env.PRERENDER_JOBS || 0) || Infinity

// ── 유틸 ────────────────────────────────────────────────────────────────
const esc = (s) =>
  String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

/** 검색결과 스니펫에 그대로 나가는 문장 — 한 줄로 눌러 담고 자른다(seo.ts 의 clip 과 같은 규칙). */
function clip(text, max = 155) {
  if (!text) return ''
  const flat = String(text).replace(/\s+/g, ' ').trim()
  return flat.length <= max ? flat : `${flat.slice(0, max - 1).trimEnd()}…`
}

function readJson(rel) {
  const p = join(PUBLIC, rel)
  if (!existsSync(p)) return null
  return JSON.parse(readFileSync(p, 'utf8'))
}

function mtime(rel) {
  const p = join(PUBLIC, rel)
  return existsSync(p) ? statSync(p).mtime.toISOString().slice(0, 10) : today
}

const today = new Date().toISOString().slice(0, 10)

// ── HTML 셸 ─────────────────────────────────────────────────────────────
const shellPath = join(DIST, 'index.html')
if (!existsSync(shellPath)) {
  console.error('[prerender] dist/index.html 이 없습니다. vite build 를 먼저 도세요.')
  process.exit(1)
}
// 첫 페이지로 dist/index.html 자신을 덮어쓰므로, 손 안 댄 셸을 따로 남겨 둔다.
// vite build 는 dist 를 통째로 비우고 다시 만들기 때문에 이 사본이 낡을 일은 없다
// (그래서 프리렌더만 다시 돌려도 항상 이번 빌드의 셸을 쓴다).
const cachePath = join(DIST, '.shell.html')
const shell = existsSync(cachePath) ? readFileSync(cachePath, 'utf8') : readFileSync(shellPath, 'utf8')
const ROOT_DIV = '<div id="root"></div>'
if (!shell.includes(ROOT_DIV)) {
  console.error('[prerender] index.html 에서 #root 를 못 찾았습니다. vite build 를 다시 도세요.')
  process.exit(1)
}
if (!existsSync(cachePath)) writeFileSync(cachePath, shell)

/**
 * 한 장을 찍는다.
 * head 태그에 data-seo 를 붙이는 이유: 브라우저에서 React 가 뜨면 seo.ts 가
 * `[data-seo]` 를 걷어내고 자기 것으로 다시 단다. 표식이 없으면 정적 메타와
 * 런타임 메타가 겹쳐 같은 태그가 두 벌씩 남는다.
 */
function page({ path, title, description, body, jsonLd, robots }) {
  const url = SITE_URL + path
  const full = `${title} | ${SITE_NAME}`
  const desc = clip(description)
  const head = [
    `<title>${esc(full)}</title>`,
    `<link rel="canonical" href="${esc(url)}" data-seo>`,
    `<meta name="description" content="${esc(desc)}" data-seo>`,
    robots ? `<meta name="robots" content="${esc(robots)}" data-seo>` : '',
    `<meta property="og:type" content="website" data-seo>`,
    `<meta property="og:site_name" content="${SITE_NAME}" data-seo>`,
    `<meta property="og:title" content="${esc(full)}" data-seo>`,
    `<meta property="og:description" content="${esc(desc)}" data-seo>`,
    `<meta property="og:url" content="${esc(url)}" data-seo>`,
    `<meta property="og:locale" content="ko_KR" data-seo>`,
    `<meta name="twitter:card" content="summary" data-seo>`,
    `<meta name="twitter:title" content="${esc(full)}" data-seo>`,
    `<meta name="twitter:description" content="${esc(desc)}" data-seo>`,
    jsonLd
      ? `<script type="application/ld+json" data-seo>${JSON.stringify(jsonLd).replace(/</g, '\\u003c')}</script>`
      : '',
  ]
    .filter(Boolean)
    .join('\n    ')

  let html = shell
  // 셸의 기본 title/description 은 페이지별 것으로 대체한다(둘이 겹치면 안 된다).
  html = html.replace(/<title>[\s\S]*?<\/title>\s*/, '')
  html = html.replace(/<meta\s+name="description"[\s\S]*?\/>\s*/, '')
  html = html.replace('</head>', `  ${head}\n  </head>`)
  // 정적 본문은 #root 안에 넣는다. 브라우저에서는 React 가 마운트하며 이 자리를
  // 통째로 갈아끼우므로 화면에는 영향이 없고, JS 를 안 도는 크롤러만 이걸 읽는다.
  html = html.replace(ROOT_DIV, `<div id="root">${body}</div>`)
  return html
}

let written = 0
function write(path, html) {
  // 주소는 퍼센트 인코딩된 형태(/companies/%EC%BF%A0%ED%8C%A1)지만 파일은 원문 이름으로
  // 깐다 — nginx 는 요청 URI 를 디코딩한 뒤 파일을 찾기 때문이다. 인코딩된 이름으로
  // 깔면 nginx 에서만 조용히 안 잡혀 SPA 폴백으로 새고, 프리렌더가 무용지물이 된다.
  const dir = join(DIST, path === '/' ? '' : decodeURIComponent(path))
  mkdirSync(dir, { recursive: true })
  writeFileSync(join(dir, 'index.html'), html)
  written += 1
}

// 모든 정적 본문에 공통으로 붙는 머리 — 크롤러가 여기서 다른 탭으로 건너간다.
const NAV = `<nav><a href="/">개발자 채용공고</a> · <a href="/companies">기업 기술스택</a> · <a href="/blog">기술블로그</a> · <a href="/radar">기술 레이더</a> · <a href="/calendar">모집 캘린더</a> · <a href="/trend">기술 트렌드</a> · <a href="/reveng">기술 역설계</a> · <a href="/mindmap">커리어 마인드맵</a> · <a href="/reposts">재공고</a></nav>`

const section = (h, text, max = 1200) =>
  text ? `<section><h2>${esc(h)}</h2><p>${esc(clip(text, max))}</p></section>` : ''

// ── 데이터 ──────────────────────────────────────────────────────────────
const jobs = readJson('all_jobs_enriched.json') ?? []
const stacks = readJson('company_stacks.json')
const radar = readJson('company_tech_radar.json')
const revengIndex = readJson('reveng/index.json')
const blogs = readJson('tech_blogs.json')

const jobKey = (j) => `${j.site}-${j.pid}` // src/lib/urls.ts 의 jobKey 와 같은 규칙
const openJobs = jobs.filter((j) => j.status !== 'closed')
// 같은 site-pid 가 두 번 들어오는 공고가 드물게 있다(원본 사이트의 중복 등록).
// 주소는 하나여야 하므로 먼저 나온 것만 남긴다.
const byKey = new Map()
for (const j of openJobs) if (!byKey.has(jobKey(j))) byKey.set(jobKey(j), j)
const jobPages = [...byKey.values()].slice(0, JOB_LIMIT)

// 회사 페이지에서 공고로 이어 주려면 원본 URL → 내부 주소 map 이 필요하다.
const pathByUrl = new Map(jobs.map((j) => [j.url, `/jobs/${jobKey(j)}`]))

const urls = [] // sitemap 재료: { loc, lastmod, changefreq, priority }
const add = (loc, lastmod, changefreq, priority) => urls.push({ loc, lastmod, changefreq, priority })

// ── 탭(허브) 페이지 ─────────────────────────────────────────────────────
// 문구는 src/lib/urls.ts 의 TAB_SEO 와 같아야 한다.
const TAB_SEO = {
  '/': {
    title: '개발자 채용공고 모아보기',
    desc: '원티드·점핏·잡코리아·사람인·데보션과 해외 원격 보드의 개발자 채용공고를 한곳에서 기술스택·경력·직무로 걸러 봅니다.',
  },
  '/companies': {
    title: '기업 기술스택 분석',
    desc: '채용공고에서 뽑아낸 회사별 기술스택·도메인·아키텍처 분석. 어떤 회사가 무엇으로 개발하는지 공고 데이터로 확인합니다.',
  },
  '/mindmap': {
    title: '개발자 커리어 마인드맵',
    desc: '직무·기술·경력 단계를 하나의 지도로 이은 개발자 커리어 마인드맵.',
  },
  '/blog': {
    title: '기업 기술블로그 모아보기',
    desc: '국내외 기업 기술블로그 글을 기술스택·카테고리로 모으고 한국어 요약과 번역을 붙였습니다.',
  },
  '/radar': {
    title: '글로벌 IT 기업 100곳 기술 레이더',
    desc: '글로벌 IT 기업 100곳의 언어·기술스택·아키텍처·채용 전형을 정리한 기술 레이더.',
  },
  '/calendar': {
    title: '개발자 채용 모집 캘린더',
    desc: '공고 마감일과 모집 시작일을 달력으로. 언제 열리고 언제 닫히는지 한눈에 봅니다.',
  },
  '/reposts': {
    title: '재공고 추적',
    desc: '같은 포지션이 반복해서 다시 올라오는 공고를 추적합니다. 자주 다시 뜨는 자리가 보입니다.',
  },
  '/trend': {
    title: '개발 기술 트렌드',
    desc: '채용공고에서 언급된 기술의 비중 변화로 보는 개발 기술 트렌드와 학습 경로.',
  },
  '/reveng': {
    title: '기업 기술 역설계',
    desc: '공개 자료만으로 재구성한 기업의 비즈니스 모델 → 도메인 → 기능 구현 → 시스템 연결.',
  },
}

// 목록 페이지의 정적 본문에는 실제 링크를 깐다. 크롤러는 이 링크를 타고 상세로
// 들어가고, 사이트맵에만 있는 주소보다 훨씬 빨리 발견된다.
const jobLinks = jobPages
  .slice(0, 300)
  .map((j) => `<li><a href="/jobs/${jobKey(j)}">${esc(j.company)} — ${esc(j.title)}</a></li>`)
  .join('')

const companyList = (stacks?.companies ?? []).filter((c) => c.posting_count >= 2)
const companyLinks = companyList
  .slice(0, 300)
  .map((c) => `<li><a href="/companies/${encodeURIComponent(c.norm)}">${esc(c.name)} 기술스택</a></li>`)
  .join('')

const radarList = radar?.companies ?? []
const radarLinks = radarList
  .map((c) => `<li><a href="/radar/${encodeURIComponent(c.key)}">${esc(c.name)} 기술스택·아키텍처</a></li>`)
  .join('')

const revengList = revengIndex?.companies ?? []
const revengLinks = revengList
  .map((c) => `<li><a href="/reveng/${encodeURIComponent(c.slug)}">${esc(c.name)} 기술 역설계</a></li>`)
  .join('')

const HUB_LINKS = {
  '/': `<h2>최근 채용공고</h2><ul>${jobLinks}</ul>`,
  '/companies': `<h2>회사 목록</h2><ul>${companyLinks}</ul>`,
  '/radar': `<h2>기업 목록</h2><ul>${radarLinks}</ul>`,
  '/reveng': `<h2>역설계한 회사</h2><ul>${revengLinks}</ul>`,
}

const jobsMtime = mtime('all_jobs_enriched.json')

for (const [path, seo] of Object.entries(TAB_SEO)) {
  write(
    path,
    page({
      path,
      title: seo.title,
      description: seo.desc,
      body: `${NAV}<main><h1>${esc(seo.title)}</h1><p>${esc(seo.desc)}</p>${HUB_LINKS[path] ?? ''}</main>`,
      jsonLd:
        path === '/'
          ? {
              '@context': 'https://schema.org',
              '@type': 'WebSite',
              name: SITE_NAME,
              url: SITE_URL,
              description: seo.desc,
            }
          : null,
    }),
  )
  add(SITE_URL + path, jobsMtime, 'daily', path === '/' ? '1.0' : '0.8')
}

// ── 공고 상세 ───────────────────────────────────────────────────────────
for (const j of jobPages) {
  const path = `/jobs/${jobKey(j)}`
  const url = SITE_URL + path
  const stack = (j.tech_stack ?? []).slice(0, 12)
  const head = [j.company, j.career, j.location].filter(Boolean).join(' · ')
  const description = clip(
    `${head}${stack.length ? ` · ${stack.slice(0, 6).join(', ')}` : ''} — ${
      j.main_tasks || j.qualifications || j.full_jd || ''
    }`,
  )
  const iso = j.deadline_date && /^\d{4}-\d{2}-\d{2}/.test(j.deadline_date) ? j.deadline_date : null

  // schema.org JobPosting — 구글 채용 검색이 읽는 형식(src/lib/urls.ts 의 jobJsonLd 와 같은 모양).
  // datePosted 는 원본이 주지 않는 공고가 대부분이라 넣지 않는다. 없는 날짜를 지어내는
  // 순간 그게 곧 잘못된 구조화 데이터다.
  const posting = {
    '@type': 'JobPosting',
    title: j.title,
    description: clip([j.main_tasks, j.qualifications, j.preferences].filter(Boolean).join('\n'), 4000),
    identifier: { '@type': 'PropertyValue', name: j.site, value: j.pid },
    hiringOrganization: { '@type': 'Organization', name: j.company },
    ...(j.location
      ? {
          jobLocation: {
            '@type': 'Place',
            address: { '@type': 'PostalAddress', addressLocality: j.location, ...(j.overseas ? {} : { addressCountry: 'KR' }) },
          },
        }
      : j.overseas
        ? { jobLocationType: 'TELECOMMUTE' }
        : {}),
    ...(iso ? { validThrough: iso } : {}),
    ...(stack.length ? { skills: (j.tech_stack ?? []).join(', ') } : {}),
    ...(j.career ? { experienceRequirements: j.career } : {}),
    url,
    sameAs: j.url,
    directApply: false,
  }
  const breadcrumb = {
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: SITE_NAME, item: `${SITE_URL}/` },
      { '@type': 'ListItem', position: 2, name: j.company, item: url },
    ],
  }

  const body =
    `${NAV}<main><article>` +
    `<h1>${esc(j.company)} ${esc(j.title)}</h1>` +
    `<p>${esc([j.site, j.career, j.location].filter(Boolean).join(' · '))}</p>` +
    (stack.length ? `<ul>${stack.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : '') +
    section('주요 업무', j.main_tasks) +
    section('자격 요건', j.qualifications) +
    section('우대 사항', j.preferences) +
    section('복지', j.benefits, 600) +
    (j.url ? `<p><a href="${esc(j.url)}" rel="nofollow noopener">원본 공고 보기</a></p>` : '') +
    `<p><a href="/">전체 개발자 채용공고</a></p>` +
    `</article></main>`

  write(
    path,
    page({
      path,
      title: `${j.company} ${j.title}`,
      description,
      body,
      jsonLd: { '@context': 'https://schema.org', '@graph': [posting, breadcrumb] },
    }),
  )
  add(url, jobsMtime, 'weekly', '0.7')
}

// ── 회사 기술스택 ───────────────────────────────────────────────────────
const stacksMtime = mtime('company_stacks.json')
for (const c of companyList) {
  const path = `/companies/${encodeURIComponent(c.norm)}`
  const tech = (c.top_tech ?? []).slice(0, 15).map((t) => t.name)
  const description = clip(
    `${c.name}의 채용공고 ${c.posting_count}건에서 뽑은 기술스택: ${tech.slice(0, 8).join(', ')}. ${c.summary ?? ''}`,
  )
  const postings = (c.postings ?? [])
    .slice(0, 30)
    .map((p) => {
      const to = pathByUrl.get(p.url)
      return to ? `<li><a href="${esc(to)}">${esc(p.title)}</a></li>` : `<li>${esc(p.title)}</li>`
    })
    .join('')
  const body =
    `${NAV}<main><article>` +
    `<h1>${esc(c.name)} 기술스택</h1>` +
    `<p>${esc(clip(c.summary, 500))}</p>` +
    (tech.length ? `<h2>주요 기술</h2><ul>${tech.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : '') +
    ((c.domains ?? []).length
      ? `<h2>도메인</h2><ul>${c.domains.slice(0, 6).map((d) => `<li>${esc(d.name)}</li>`).join('')}</ul>`
      : '') +
    (postings ? `<h2>채용공고</h2><ul>${postings}</ul>` : '') +
    `<p><a href="/companies">전체 기업 기술스택</a></p>` +
    `</article></main>`
  write(
    path,
    page({
      path,
      title: `${c.name} 기술스택·채용공고`,
      description,
      body,
      jsonLd: {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: c.name,
        ...(c.homepage ? { url: c.homepage } : {}),
        description: clip(c.summary, 300),
        knowsAbout: tech,
      },
    }),
  )
  add(SITE_URL + path, stacksMtime, 'weekly', '0.6')
}

// ── 기술 레이더(글로벌 100곳) ───────────────────────────────────────────
const radarMtime = mtime('company_tech_radar.json')
for (const c of radarList) {
  const path = `/radar/${encodeURIComponent(c.key)}`
  const langs = (c.languages ?? []).join(', ')
  const description = clip(`${c.name}(${c.domain})의 기술스택과 아키텍처. 언어: ${langs}. ${c.summary ?? ''}`)
  const stackAll = ['backend', 'frontend', 'data', 'infra']
    .flatMap((k) => c.stack?.[k] ?? [])
    .slice(0, 30)
  const body =
    `${NAV}<main><article>` +
    `<h1>${esc(c.name)} 기술스택·아키텍처</h1>` +
    `<p>${esc(clip(c.summary, 600))}</p>` +
    (langs ? `<h2>주요 언어</h2><p>${esc(langs)}</p>` : '') +
    (stackAll.length ? `<h2>기술스택</h2><ul>${stackAll.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : '') +
    ((c.architecture ?? []).length
      ? `<h2>아키텍처</h2><ul>${c.architecture.map((a) => `<li>${esc(a)}</li>`).join('')}</ul>`
      : '') +
    section('왜 이 언어인가', c.why_language, 800) +
    section('왜 이 아키텍처인가', c.why_architecture, 800) +
    `<p><a href="/radar">기업 100곳 기술 레이더</a></p>` +
    `</article></main>`
  write(path, page({ path, title: `${c.name} 기술스택·아키텍처`, description, body }))
  add(SITE_URL + path, radarMtime, 'monthly', '0.6')
}

// ── 기술 역설계 ─────────────────────────────────────────────────────────
for (const c of revengList) {
  const path = `/reveng/${encodeURIComponent(c.slug)}`
  const detail = readJson(`reveng/companies/${c.slug}.json`)
  const features = (detail?.features ?? []).slice(0, 20).map((f) => f.title ?? f.name).filter(Boolean)
  const description = clip(`${c.name}(${c.name_en ?? ''}) 기술 역설계 — ${c.one_liner ?? ''}`)
  const body =
    `${NAV}<main><article>` +
    `<h1>${esc(c.name)} 기술 역설계</h1>` +
    `<p>${esc(c.one_liner ?? '')}</p>` +
    section('비즈니스 모델', detail?.business_model?.summary ?? detail?.summary, 800) +
    (features.length ? `<h2>재구성한 기능</h2><ul>${features.map((f) => `<li>${esc(f)}</li>`).join('')}</ul>` : '') +
    `<p><a href="/reveng">전체 역설계 목록</a></p>` +
    `</article></main>`
  write(path, page({ path, title: `${c.name} 기술 역설계`, description, body }))
  add(SITE_URL + path, c.updated_at ?? today, 'monthly', '0.6')
}

// 기술블로그 글 상세는 남의 글을 옮겨 놓은 화면이다. 주소는 있어야 하지만(공유·뒤로가기)
// 색인은 원문이 가져가는 게 맞으므로 사이트맵에 넣지 않고 프리렌더도 하지 않는다.
// 런타임 메타는 seo.ts 가 붙인다.
const blogCount = blogs?.posts?.length ?? 0

// ── sitemap ─────────────────────────────────────────────────────────────
// 한 파일 5만 URL·10MB 제한이 있어 2만 개씩 쪼개고 인덱스로 묶는다.
const CHUNK = 20000
const chunks = []
for (let i = 0; i < urls.length; i += CHUNK) chunks.push(urls.slice(i, i + CHUNK))

chunks.forEach((chunk, i) => {
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    chunk
      .map(
        (u) =>
          `  <url><loc>${esc(u.loc)}</loc><lastmod>${u.lastmod}</lastmod>` +
          `<changefreq>${u.changefreq}</changefreq><priority>${u.priority}</priority></url>`,
      )
      .join('\n') +
    `\n</urlset>\n`
  writeFileSync(join(DIST, `sitemap-${i + 1}.xml`), xml)
})

const index =
  `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
  chunks
    .map((_, i) => `  <sitemap><loc>${SITE_URL}/sitemap-${i + 1}.xml</loc><lastmod>${today}</lastmod></sitemap>`)
    .join('\n') +
  `\n</sitemapindex>\n`
writeFileSync(join(DIST, 'sitemap.xml'), index)

// robots.txt — 검색어가 붙은 목록은 같은 목록의 무한 변형이라 크롤 예산만 태운다.
writeFileSync(
  join(DIST, 'robots.txt'),
  `User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /*?q=\n\nSitemap: ${SITE_URL}/sitemap.xml\n`,
)

console.log(
  `[prerender] ${written}쪽 (공고 ${jobPages.length} · 회사 ${companyList.length} · 레이더 ${radarList.length} · 역설계 ${revengList.length})\n` +
    `[prerender] sitemap ${chunks.length}개 · URL ${urls.length}개 · 블로그 글 ${blogCount}건은 색인 제외\n` +
    `[prerender] 오리진 ${SITE_URL}`,
)
