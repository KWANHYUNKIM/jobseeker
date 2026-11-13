import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { BlogContent, BlogPost } from '../../../types'
import { useLocale } from '../utils/locale'
import { blendByEngagement, useEngagement } from '../../../hooks/useEngagement'
import { useSimilarPosts } from '../../../hooks/useSimilar'
import { track, useDwell } from '../../../utils/track'
import { paths } from '../../../utils/urls'
import { onLinkClick } from '../../../utils/navigation'
import { SiteFooter } from '../../../components/SiteFooter'
import { CompanyMark } from '../../../components/ui'
import { docFetch } from '../../../api/client'

const COUNTRY_LABEL: Record<string, string> = {
  KR: '🇰🇷 한국', US: '🇺🇸 미국', JP: '🇯🇵 일본', DE: '🇩🇪 독일',
  GB: '🇬🇧 영국', IN: '🇮🇳 인도', SG: '🇸🇬 싱가포르',
}

type View = 'ko' | 'orig'

// 영상 링크 → 임베드 URL (없으면 null)
function videoEmbed(href?: string): string | null {
  if (!href) return null
  try {
    const u = new URL(href, 'https://x')
    const host = u.hostname.replace(/^www\./, '')
    if (host === 'tv.naver.com' && u.pathname.includes('/embed/'))
      return href.replace('autoPlay=true', 'autoPlay=false')
    if (host === 'youtube.com' && u.searchParams.get('v'))
      return `https://www.youtube.com/embed/${u.searchParams.get('v')}`
    if (host === 'youtu.be') return `https://www.youtube.com/embed${u.pathname}`
    if (host === 'youtube.com' && u.pathname.startsWith('/embed/')) return href
    if (host === 'player.vimeo.com') return href
    if (host === 'vimeo.com') return `https://player.vimeo.com/video${u.pathname}`
  } catch {
    return null
  }
  return null
}

const VIDEO_FILE = /\.(mp4|webm|ogg)(\?|$)/i

/**
 * 블로그 글 상세 — 팝업이 아니라 화면 하나.
 *
 * 원래는 모달이었다. 그런데 여기 들어오는 건 끝까지 읽는 글이다 — 코드 블록과
 * 아키텍처 그림이 들어간 남의 기술 글을, 어두운 장막 뒤 3xl 칸에 넣어 두면
 * 가로로 넘치고 세로로 길어져 읽다 말게 된다. 공고 상세와 같이 목록을 통째로
 * 갈아끼우는 전체 화면으로 두고, 남는 폭은 '비슷한 글' 이 가져간다.
 */
export function BlogDetail({
  post,
  onClose,
  onOpenUrl,
  allPosts = [],
}: {
  post: BlogPost
  onClose: () => void
  /** 비슷한 글을 눌렀을 때 그 글로 갈아끼운다. 없으면 추천 섹션을 감춘다. */
  onOpenUrl?: (url: string) => void
  /** 전체 글 — 오른쪽 '이 회사 글 N개' 를 센다. */
  allPosts?: BlogPost[]
}) {
  const [content, setContent] = useState<BlogContent | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'pending' | 'error'>('loading')
  const [view, setView] = useState<View>('ko')
  const { items: similarItems } = useSimilarPosts(onOpenUrl ? post.url : null)
  const eng = useEngagement()
  const similar = onOpenUrl ? blendByEngagement(similarItems, eng, post.url) : []

  useDwell(post.url)
  useEffect(() => {
    track('view', post.url)
  }, [post.url])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    let cancelled = false
    if (!post.content_id) {
      setState('pending')
      return
    }
    setState('loading')
    docFetch(`/blog_content/${post.content_id}.json`)
      .then((r) => {
        // 본문 파일이 없으면 404 가 아니라 SPA 폴백(index.html, 200)이 온다 — vite 개발 서버도
        // 운영 nginx 도 그렇다. 그걸 JSON 으로 읽다 깨져 '불러오지 못했습니다'가 떴다.
        // JSON 이 아니면 '아직 수집 전'이다.
        const isJson = (r.headers.get('content-type') ?? '').includes('json')
        if (r.status === 404 || (r.ok && !isJson)) {
          if (!cancelled) setState('pending')
          return null
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: BlogContent | null) => {
        if (cancelled || !data) return
        setContent(data)
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [post.content_id])

  // 무엇을 먼저 보여줄지는 보는 사람의 언어가 정한다. 한국어 사용자에게는 번역이,
  // 그 외에는 원문이 기본이다 — 영어권 사용자에게 기계 번역된 한국어를 먼저 들이미는
  // 것은 원문이 이미 그 사람의 언어인데도 굳이 한 겹 씌우는 셈이다.
  // (한국어 글은 translated 가 false 라 어느 쪽이든 원문으로 간다.)
  const locale = useLocale()
  useEffect(() => {
    if (content) setView(locale === 'ko' && content.translated ? 'ko' : 'orig')
  }, [content, locale])

  const body =
    content && (view === 'ko' && content.translated ? content.content_ko : content.content)

  // 목차 — 본문의 ## · ### 머리. 누르면 그 자리로 내려간다(머리마다 id 를 단다).
  const toc = useMemo(() => tocOf(body || ''), [body])
  const [tocOn, setTocOn] = useState<string | null>(null)
  // 읽는 데 걸리는 시간 — 영어는 분당 200 단어, 한국어는 분당 500 자
  const minutes = useMemo(() => {
    const t = body || ''
    if (!t) return null
    const words = view === 'orig' && content?.lang !== 'ko' ? t.split(/\s+/).length / 200 : t.replace(/\s/g, '').length / 500
    return Math.max(1, Math.round(words))
  }, [body, view, content?.lang])
  // 한 줄 요약 — 번역이 있으면 번역 본문의 첫 문장, 없으면 피드가 준 요약의 첫 문장
  const oneLine = useMemo(() => firstSentence(content?.translated ? content.content_ko : post.summary), [content, post.summary])
  const sameCompany = allPosts.filter((p) => p.company === post.company).length
  const companyTo = `${paths.blog()}?company=${encodeURIComponent(post.company)}`

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <nav aria-label="경로" className="text-sm text-[#777]">
          <a
            href={paths.blog()}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
              e.preventDefault()
              onClose()
            }}
            className="hover:text-[#272727]"
            title="목록으로 (ESC)"
          >
            기술 블로그
          </a>{' '}
          › {post.company}
        </nav>

        <div className="mt-6 flex flex-col lg:flex-row gap-[30px] items-start">
          <article className="w-full lg:flex-1 min-w-0 rounded-[30px] border border-[#e2e8ec] bg-white">
            <header className="px-6 sm:px-11 pt-9 pb-8 border-b border-[#e2e8ec]">
              <div className="flex items-center gap-3">
                <span className="grid place-items-center w-11 h-11 rounded-xl overflow-hidden shrink-0">
                  <CompanyMark name={post.company} size={44} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-base font-bold text-[#272727]">{post.company}</span>
                    <span className="rounded bg-[#f4f4f4] px-1.5 text-xs leading-5 text-[#474747]">{COUNTRY_LABEL[post.country]?.split(' ')[1] ?? post.country}</span>
                  </span>
                  <span className="block text-[13px] text-[#999] tabular-nums">
                    {post.published}
                    {content && ` · ${view === 'ko' && content.translated ? '한국어 번역' : content.lang === 'ko' ? '원문' : '영문 원문'}`}
                    {minutes && ` · 읽는 데 약 ${minutes}분`}
                  </span>
                </span>
                <LikeButton id={post.url} />
                <ShareButton />
              </div>
              <h1 className="mt-6 text-[34px] font-bold leading-[47px] tracking-[-0.6px] text-[#272727] break-words">{post.title}</h1>
              {post.categories.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {post.categories.map((c) => (
                    <span key={c} className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] text-[#474747]">
                      #{c}
                    </span>
                  ))}
                </div>
              )}
              {oneLine && (
                <div className="mt-[22px] rounded-[20px] bg-(--color-accent-weak) px-6 py-5">
                  <div className="text-[13px] font-medium text-(--color-accent)">한 줄 요약</div>
                  <p className="mt-1 text-[15px] leading-[24px] text-[#272727]">{oneLine}</p>
                </div>
              )}
            </header>

            <div className="px-6 sm:px-11 pt-9 pb-11">
              {state === 'loading' && <div className="text-[#999]">본문 불러오는 중…</div>}
              {state === 'error' && <div className="text-(--color-red-400)">본문을 불러오지 못했습니다.</div>}
              {state === 'pending' && (
                <div className="rounded-2xl bg-[#f7f9fa] px-6 py-5 text-[#666]">
                  {post.content_state === 'blocked'
                    ? '이 블로그는 본문 수집이 막혀 있어요. (사이트 봇 차단 — 원본에서 읽어 주세요)'
                    : '본문이 아직 수집되지 않았어요. (크롤이 회차당 일부씩 수집 중)'}
                </div>
              )}
              {state === 'ready' && (
                <>
                  {view === 'ko' && content?.translated && <div className="mb-4 text-xs text-[#999]">※ 기계 번역(무료 엔진) — 정확한 내용은 원문을 확인하세요.</div>}
                  <div className="blog-md blog-md-lg text-[#272727]">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ children }) => <h2 id={anchorOf(children)}>{children}</h2>,
                        h2: ({ children }) => <h2 id={anchorOf(children)}>{children}</h2>,
                        h3: ({ children }) => <h3 id={anchorOf(children)}>{children}</h3>,
                        // 줄 전체가 굵은 글씨면 머리로 그린다 — 목차(tocOf)와 같은 규칙
                        p({ node, children }) {
                          const kids = node?.children ?? []
                          const only = kids.length === 1 && kids[0].type === 'element' && kids[0].tagName === 'strong'
                          return only ? <h2 id={anchorOf(children)}>{children}</h2> : <p>{children}</p>
                        },
                        a({ href, children }) {
                          const embed = videoEmbed(href)
                          if (embed)
                            return (
                              <span className="blog-video">
                                <iframe
                                  src={embed}
                                  title="video"
                                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                  allowFullScreen
                                />
                              </span>
                            )
                          if (href && VIDEO_FILE.test(href)) return <video src={href} controls className="blog-video-file" />
                          return (
                            <a href={href} target="_blank" rel="noreferrer">
                              {children}
                            </a>
                          )
                        },
                      }}
                    >
                      {body || ''}
                    </ReactMarkdown>
                  </div>
                </>
              )}

              <div className="mt-10 flex flex-wrap gap-2.5">
                <a
                  href={post.url}
                  onClick={() => track('click', 'outbound', post.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 h-11 px-6 rounded-md bg-(--color-accent) text-base font-bold text-white hover:bg-(--color-accent-deep)"
                >
                  원본 페이지에서 보기
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="1.4" aria-hidden>
                    <path d="M5 2H2v8h8V7M7 1.5h3.5V5M10.5 1.5 5.5 6.5" />
                  </svg>
                </a>
                {content?.translated && (
                  <button
                    type="button"
                    onClick={() => setView(view === 'ko' ? 'orig' : 'ko')}
                    className="h-11 px-5 rounded-[22px] border border-(--color-accent) bg-white text-sm font-medium text-(--color-accent) hover:bg-(--color-accent-weak)"
                  >
                    {view === 'ko' ? '원문 보기' : '한국어 번역 보기'}
                  </button>
                )}
              </div>
            </div>
          </article>

          {/* 오른쪽 칸 — 목차 · 비슷한 글 · 이 회사 글 */}
          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4 lg:sticky lg:top-4">
            {toc.length > 0 && (
              <SideBox title="목차">
                <ol className="mt-3 flex flex-col">
                  {toc.map((h) => (
                    <li key={h.id}>
                      <a
                        href={`#${h.id}`}
                        onClick={(e) => {
                          e.preventDefault()
                          setTocOn(h.id)
                          document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                        }}
                        className={'block py-1.5 text-sm truncate ' + (h.depth > 2 ? 'pl-5 ' : 'pl-2 ') + ((tocOn ?? toc[0].id) === h.id ? 'text-(--color-accent)' : 'text-[#666] hover:text-[#272727]')}
                      >
                        {h.text}
                      </a>
                    </li>
                  ))}
                </ol>
              </SideBox>
            )}
            {similar.length > 0 && onOpenUrl && (
              <SideBox title="비슷한 글">
                <ul className="mt-3 flex flex-col gap-3">
                  {similar.slice(0, 5).map((s) => (
                    <li key={s.url}>
                      <button
                        type="button"
                        onClick={() => {
                          track('click', s.url, post.url)
                          onOpenUrl(s.url)
                        }}
                        className="group w-full flex gap-3 text-left"
                      >
                        <span className="grid place-items-center w-8 h-8 rounded-lg overflow-hidden shrink-0">
                          <CompanyMark name={s.company} size={32} />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-sm font-medium leading-5 text-[#272727] line-clamp-2 group-hover:underline underline-offset-2">{s.title || s.url}</span>
                          <span className="mt-0.5 block text-xs text-[#999]">
                            {s.company} · <span className="text-(--color-accent)">유사도 {Math.round(s.score * 100)}%</span>
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </SideBox>
            )}
            <div className="rounded-[22px] bg-[#f3f6f8] px-[22px] py-[22px]">
              <div className="text-[17px] font-bold text-[#272727]">
                {post.company} 글 {sameCompany}개
              </div>
              <p className="mt-1 text-sm text-[#666]">{post.company} 기술 블로그의 최근 글을 모아 볼 수 있어요.</p>
              <a
                href={companyTo}
                onClick={onLinkClick(companyTo)}
                className="mt-4 w-full inline-flex items-center justify-center gap-2 h-11 rounded-[30px] bg-[#272727] text-[15px] font-medium text-white hover:bg-black"
              >
                {post.company} 글 전체 보기
                <svg width="8" height="10" viewBox="0 0 8 10" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M2.5 1.5 6 5l-3.5 3.5" />
                </svg>
              </a>
            </div>
          </aside>
        </div>
      </div>
      <SiteFooter />
    </div>
  )
}

/** 마크다운 머리(## · ###)로 목차를 만든다. 코드 블록 안의 # 은 건너뛴다. */
function tocOf(md: string): { id: string; text: string; depth: number }[] {
  const out: { id: string; text: string; depth: number }[] = []
  let fence = false
  for (const line of md.split('\n')) {
    if (/^\s*```/.test(line)) fence = !fence
    if (fence) continue
    // 머리는 ## 줄이거나, 한 줄 전체가 굵은 글씨인 줄(RSS 를 옮긴 본문은 머리를 **…** 로 적는다)
    const h = /^(#{1,3})\s+(.+?)\s*#*$/.exec(line)
    const b = h ? null : /^\s*\*\*([^*]+)\*\*\s*$/.exec(line)
    const m = h ? h : b ? ['', '##', b[1]] : null
    if (!m) continue
    const text = m[2].replace(/[*_`[\]]/g, '').replace(/\(.*?\)/g, '').trim()
    if (text) out.push({ id: slugOf(text), text, depth: Math.max(2, m[1].length) })
  }
  return out.slice(0, 20)
}

function slugOf(text: string): string {
  return 'h-' + text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').slice(0, 60)
}

/** ReactMarkdown 머리 자식 → 목차와 같은 id */
function anchorOf(children: React.ReactNode): string {
  const flat = (n: React.ReactNode): string =>
    typeof n === 'string' || typeof n === 'number'
      ? String(n)
      : Array.isArray(n)
        ? n.map(flat).join('')
        : n && typeof n === 'object' && 'props' in n
          ? flat((n as { props: { children?: React.ReactNode } }).props.children)
          : ''
  return slugOf(flat(children).replace(/[*_`[\]]/g, '').trim())
}

/** 첫 문장 — 마크다운 기호를 걷어 내고 140자 안에서 자른다. */
function firstSentence(text: string | undefined): string {
  if (!text) return ''
  const plain = text
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith('#') && !l.startsWith('!') && !l.startsWith('```') && !l.startsWith('|'))
  if (!plain) return ''
  const t = plain.replace(/[*_`>]/g, '').replace(/\[(.*?)\]\(.*?\)/g, '$1')
  const m = /^(.{20,}?[.!?。])(\s|$)/.exec(t)
  const s = m ? m[1] : t
  return s.length > 140 ? s.slice(0, 139) + '…' : s
}

function SideBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-[22px] border border-[#e2e8ec] bg-white px-[22px] pt-[22px] pb-[18px]">
      <h2 className="text-[17px] font-bold text-[#272727]">{title}</h2>
      {children}
    </section>
  )
}

const LIKE_KEY = 'jd-blog-likes'

/** 마음에 든 글 — 이 브라우저에만 남는다. */
function LikeButton({ id }: { id: string }) {
  const read = (): string[] => {
    try {
      return JSON.parse(localStorage.getItem(LIKE_KEY) || '[]') as string[]
    } catch {
      return []
    }
  }
  const [on, setOn] = useState(() => read().includes(id))
  const flip = () => {
    const cur = new Set(read())
    if (cur.has(id)) cur.delete(id)
    else cur.add(id)
    try {
      localStorage.setItem(LIKE_KEY, JSON.stringify([...cur]))
    } catch {
      /* 저장소가 막힌 브라우저 */
    }
    setOn(cur.has(id))
  }
  return (
    <button type="button" onClick={flip} aria-pressed={on} aria-label="마음에 든 글">
      <svg width="20" height="20" viewBox="0 0 22 22" fill={on ? '#f45757' : 'none'} stroke={on ? '#f45757' : '#999'} strokeWidth="1.6" aria-hidden>
        <path d="M11 18s-6.5-4-6.5-8.5A3.5 3.5 0 0 1 11 7.2a3.5 3.5 0 0 1 6.5 2.3C17.5 14 11 18 11 18Z" />
      </svg>
    </button>
  )
}

function ShareButton() {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      aria-label="주소 복사"
      title={done ? '주소를 복사했어요' : '주소 복사'}
      onClick={() =>
        navigator.clipboard?.writeText(window.location.href).then(
          () => {
            setDone(true)
            setTimeout(() => setDone(false), 1500)
          },
          () => {},
        )
      }
    >
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke={done ? '#f45757' : '#999'} strokeWidth="1.5" aria-hidden>
        <circle cx="15" cy="4.5" r="2.2" />
        <circle cx="5" cy="10" r="2.2" />
        <circle cx="15" cy="15.5" r="2.2" />
        <path d="M7 9 13 5.6M7 11l6 3.4" />
      </svg>
    </button>
  )
}
