import { useEffect, useState } from 'react'
import type { BlogContent, BlogPost } from '../types'

const COUNTRY_LABEL: Record<string, string> = {
  KR: '🇰🇷 한국', US: '🇺🇸 미국', JP: '🇯🇵 일본', DE: '🇩🇪 독일',
  GB: '🇬🇧 영국', IN: '🇮🇳 인도', SG: '🇸🇬 싱가포르',
}

type View = 'ko' | 'orig'

export function BlogDetail({ post, onClose }: { post: BlogPost; onClose: () => void }) {
  const [content, setContent] = useState<BlogContent | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'pending' | 'error'>('loading')
  const [view, setView] = useState<View>('ko')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
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
        setView(data.translated ? 'ko' : 'orig')
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [post.content_id])

  const body =
    content && (view === 'ko' && content.translated ? content.content_ko : content.content)

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      onClick={onClose}
    >
      <div
        className="relative bg-(--color-panel) border border-(--color-border) rounded-lg w-full max-w-3xl my-4 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="sticky top-0 z-10 bg-(--color-panel)/95 backdrop-blur border-b border-(--color-border) rounded-t-lg px-6 py-4">
          <div className="flex items-center gap-2 text-xs text-(--color-muted) mb-1">
            <span className="text-(--color-accent) font-medium">{post.company}</span>
            <span>{COUNTRY_LABEL[post.country] ?? post.country}</span>
            {post.published && <span>· {post.published}</span>}
            <button onClick={onClose} className="ml-auto text-(--color-muted) hover:text-(--color-text) text-lg leading-none">
              ✕
            </button>
          </div>
          <h2 className="text-(--color-text) font-semibold text-lg">{post.title}</h2>
          <div className="mt-2 flex items-center gap-2">
            {content?.translated && (
              <div className="flex rounded overflow-hidden border border-(--color-border) text-xs">
                <ViewBtn active={view === 'ko'} onClick={() => setView('ko')}>한국어 번역</ViewBtn>
                <ViewBtn active={view === 'orig'} onClick={() => setView('orig')}>원문</ViewBtn>
              </div>
            )}
            <a
              href={post.url}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-(--color-accent) hover:underline ml-auto"
            >
              ↗ 원본 페이지
            </a>
          </div>
        </div>

        {/* 본문 */}
        <div className="px-6 py-5">
          {state === 'loading' && <div className="text-(--color-muted)">본문 불러오는 중…</div>}
          {state === 'error' && <div className="text-red-400">본문을 불러오지 못했습니다.</div>}
          {state === 'pending' && (
            <div className="text-(--color-muted)">
              본문이 아직 수집되지 않았습니다. (크롤이 회차당 일부씩 수집 중)
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
              <article className="whitespace-pre-wrap leading-relaxed text-(--color-text) text-[0.95rem]">
                {body}
              </article>
            </>
          )}
        </div>
      </div>
    </div>
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
        active ? 'bg-(--color-accent) text-black font-medium' : 'text-(--color-text) hover:bg-(--color-bg)'
      }`}
    >
      {children}
    </button>
  )
}
