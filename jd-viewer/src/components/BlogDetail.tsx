import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { BlogContent, BlogPost } from '../types'
import { useLocale } from '../lib/locale'
import { blendByEngagement, useEngagement } from '../lib/useEngagement'
import { useSimilarPosts, type SimilarItem } from '../lib/useSimilar'
import { track, useDwell } from '../lib/track'
import { paths } from '../lib/urls'
import { CompanyMark } from './ui'

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
}: {
  post: BlogPost
  onClose: () => void
  /** 비슷한 글을 눌렀을 때 그 글로 갈아끼운다. 없으면 추천 섹션을 감춘다. */
  onOpenUrl?: (url: string) => void
}) {
  const [content, setContent] = useState<BlogContent | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'pending' | 'error'>('loading')
  const [view, setView] = useState<View>('ko')
  const { lookup } = useSimilarPosts()
  const eng = useEngagement()
  const similar = onOpenUrl ? blendByEngagement(lookup(post.url), eng, post.url) : []

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
    fetch(`/blog_content/${post.content_id}.json`)
      .then((r) => {
        if (r.status === 404) {
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

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 헤더 */}
      <div className="border-b border-(--color-border) bg-(--color-panel) px-4 sm:px-6 py-3 shrink-0">
        <div className="flex items-start gap-3">
          <a
            href={paths.blog()}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
              e.preventDefault()
              onClose()
            }}
            className="shrink-0 mt-0.5 px-2.5 py-1.5 rounded border border-(--color-border) text-xs text-(--color-muted) hover:text-(--color-text) hover:bg-(--hover)"
            title="목록으로 (ESC)"
          >
            ← 목록
          </a>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-(--color-muted) mb-1">
              <span className="inline-flex items-center gap-1.5">
                <CompanyMark name={post.company} size={15} />
                <span className="text-(--color-accent) font-medium">{post.company}</span>
              </span>
              <span>{COUNTRY_LABEL[post.country] ?? post.country}</span>
              {post.published && <span>· {post.published}</span>}
              {post.categories.length > 0 && <span>· {post.categories.join(' · ')}</span>}
            </div>
            <h2 className="text-(--color-text) text-lg sm:text-xl font-semibold leading-snug break-words">
              {post.title}
            </h2>
          </div>
          <a
            href={post.url}
            onClick={() => track('click', 'outbound', post.url)}
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex shrink-0 items-center gap-1.5 px-3 py-1.5 rounded bg-(--color-accent) text-(--color-on-accent) text-sm font-medium hover:opacity-90"
          >
            원본 페이지 ↗
          </a>
        </div>

        {content?.translated && (
          <div className="mt-3 flex rounded-md overflow-hidden border border-(--color-border) text-xs w-fit">
            <ViewBtn active={view === 'ko'} onClick={() => setView('ko')}>한국어 번역</ViewBtn>
            <ViewBtn active={view === 'orig'} onClick={() => setView('orig')}>원문</ViewBtn>
          </div>
        )}
      </div>

      {/* 본문 + 오른쪽 추천 */}
      <div className="flex flex-1 min-h-0">
        <div data-scroll className="flex-1 min-w-0 overflow-auto px-4 sm:px-8 py-6">
          <div className="mx-auto max-w-[52rem]">
            {state === 'loading' && <div className="text-(--color-muted)">본문 불러오는 중…</div>}
            {state === 'error' && <div className="text-red-400">본문을 불러오지 못했습니다.</div>}
            {state === 'pending' && (
              <div className="text-(--color-muted)">
                {post.content_state === 'blocked'
                  ? '이 블로그는 본문 수집이 막혀 있습니다. (사이트 봇 차단 — 원본에서 읽어주세요)'
                  : '본문이 아직 수집되지 않았습니다. (크롤이 회차당 일부씩 수집 중)'}
                <br />
                <a href={post.url} target="_blank" rel="noreferrer" className="text-(--color-accent) hover:underline">
                  원본 페이지에서 읽기 ↗
                </a>
              </div>
            )}
            {state === 'ready' && (
              <>
                {view === 'ko' && content?.translated && (
                  <div className="mb-3 text-xs text-(--color-muted)">
                    ※ 기계 번역(무료 엔진) — 정확한 내용은 원문을 확인하세요.
                  </div>
                )}
                <article className="blog-md text-(--color-text)">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
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
                        if (href && VIDEO_FILE.test(href))
                          return <video src={href} controls className="blog-video-file" />
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
                </article>
              </>
            )}

            <div className="mt-8 border-t border-(--color-border) pt-4">
              <a
                href={post.url}
                onClick={() => track('click', 'outbound', post.url)}
                target="_blank"
                rel="noreferrer"
                className="text-sm text-(--color-accent) hover:underline"
              >
                ↗ 원본 페이지에서 보기
              </a>
            </div>

            {/* 오른쪽 단이 없는 폭에서는 본문 아래로 흘린다. */}
            {similar.length > 0 && onOpenUrl && (
              <section className="xl:hidden mt-6 border-t border-(--color-border) pt-4">
                <SimilarHeading />
                <SimilarList items={similar} from={post.url} onOpenUrl={onOpenUrl} />
              </section>
            )}
          </div>
        </div>

        {similar.length > 0 && onOpenUrl && (
          <aside
            data-scroll
            className="hidden xl:block w-80 shrink-0 border-l border-(--color-border) overflow-auto px-4 py-6"
          >
            <SimilarHeading />
            <SimilarList items={similar} from={post.url} onOpenUrl={onOpenUrl} />
          </aside>
        )}
      </div>
    </div>
  )
}

function SimilarHeading() {
  return (
    <h3 className="text-xs uppercase tracking-wider text-(--color-muted) mb-2.5 font-medium">
      비슷한 글
    </h3>
  )
}

function SimilarList({
  items,
  from,
  onOpenUrl,
}: {
  items: SimilarItem[]
  from: string
  onOpenUrl: (url: string) => void
}) {
  return (
    <ul className="space-y-1.5">
      {items.map((s) => (
        <li key={s.url}>
          <button
            onClick={() => {
              track('click', s.url, from)
              onOpenUrl(s.url)
            }}
            className="w-full text-left px-3 py-2.5 rounded border border-(--color-border) hover:bg-(--hover) hover:border-(--color-accent)/40 flex items-center gap-3"
          >
            <span className="flex-1 min-w-0">
              <span className="block text-(--color-text) text-[13px] leading-snug truncate">
                {s.title || s.url}
              </span>
              {s.company && (
                <span className="block text-(--color-muted) text-xs mt-0.5 truncate">
                  {s.company}
                </span>
              )}
            </span>
            <span
              className="text-xs text-(--color-muted) shrink-0 tabular-nums"
              title={`코사인 유사도 ${s.score.toFixed(3)}`}
            >
              {Math.round(s.score * 100)}%
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function ViewBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1 transition ${
        active ? 'bg-(--color-accent) text-(--color-on-accent) font-medium' : 'text-(--color-text) hover:bg-(--color-bg)'
      }`}
    >
      {children}
    </button>
  )
}
