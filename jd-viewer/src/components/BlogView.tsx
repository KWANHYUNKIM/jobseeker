import { useMemo, useState } from 'react'
import { useBlogs } from '../lib/useBlogs'
import { usePaged } from '../lib/usePaged'
import { BlogDetail } from './BlogDetail'
import { goBack, navigate } from '../lib/router'
import { blogKey, paths } from '../lib/urls'
import { absUrl, clip, useSeo } from '../lib/seo'
import { Loader, ErrorState, SidePanel, MobileBar, TechIcon, CompanyMark, Pagination } from './ui'
import type { BlogPost } from '../types'

const PAGE_SIZE = 20

const COUNTRY_LABEL: Record<string, string> = {
  KR: '🇰🇷 한국',
  US: '🇺🇸 미국',
  JP: '🇯🇵 일본',
  DE: '🇩🇪 독일',
  GB: '🇬🇧 영국',
  IN: '🇮🇳 인도',
  SG: '🇸🇬 싱가포르',
}

export function BlogView({ postId }: { postId?: string | null }) {
  const { data, loading, error } = useBlogs()
  const [query, setQuery] = useState('')
  const [stacks, setStacks] = useState<Set<string>>(new Set())
  const [country, setCountry] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())
  const [navOpen, setNavOpen] = useState(false)

  // 매 렌더마다 새 배열이 되면 아래 useMemo 들이 전부 다시 돈다(글 1천여 건 × 필터).
  const posts = useMemo(() => data?.posts ?? [], [data])
  // 열려 있는 글은 주소(/blog/<id>)에서 나온다 — 글 하나하나가 공유 가능한 링크가 된다.
  const selected = useMemo(
    () => (postId ? (posts.find((p) => blogKey(p) === postId) ?? null) : null),
    [posts, postId],
  )
  const openPost = (p: BlogPost) => navigate(paths.blogPost(blogKey(p)))

  // 글 상세는 남의 글을 옮겨 놓은 화면이다. 주소는 있어야 하지만(공유·뒤로가기)
  // 색인은 원문이 가져가는 게 맞으므로 noindex 로 둔다 — 사이트맵에도 넣지 않는다.
  useSeo(
    selected
      ? {
          title: `${selected.title} — ${selected.company} 기술블로그`,
          description: clip(selected.summary || selected.title),
          canonical: absUrl(paths.blogPost(blogKey(selected))),
          robots: 'noindex, follow',
        }
      : null,
  )
  const tagCat = data?.tag_categories ?? {}
  const catOrder = data?.categories ?? []

  // 기술 키워드 빈도
  const stackCount = useMemo(() => {
    const c = new Map<string, number>()
    for (const p of posts) for (const t of p.tech_stack) c.set(t, (c.get(t) ?? 0) + 1)
    return c
  }, [posts])

  // 카테고리 → [태그, 빈도] (카테고리 순서대로, 카테고리 내 빈도순)
  const grouped = useMemo(() => {
    const g = new Map<string, [string, number][]>()
    for (const [tag, n] of stackCount) {
      const cat = tagCat[tag] ?? '기타'
      if (!g.has(cat)) g.set(cat, [])
      g.get(cat)!.push([tag, n])
    }
    for (const arr of g.values()) arr.sort((a, b) => b[1] - a[1])
    const order = [...catOrder, '기타']
    return order.filter((c) => g.has(c)).map((c) => [c, g.get(c)!] as const)
  }, [stackCount, tagCat, catOrder])

  const countries = useMemo(() => {
    const c = new Map<string, number>()
    for (const p of posts) c.set(p.country, (c.get(p.country) ?? 0) + 1)
    return [...c.entries()].sort((a, b) => b[1] - a[1])
  }, [posts])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return posts.filter((p) => {
      if (country && p.country !== country) return false
      if (stacks.size && !p.tech_stack.some((t) => stacks.has(t))) return false
      if (q) {
        const hay = `${p.title} ${p.summary} ${p.company} ${p.tags.join(' ')} ${p.tech_stack.join(
          ' ',
        )}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [posts, query, stacks, country])

  const toggleStack = (name: string) => {
    const next = new Set(stacks)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setStacks(next)
  }
  const toggleCat = (cat: string) => {
    const next = new Set(collapsed)
    if (next.has(cat)) next.delete(cat)
    else next.add(cat)
    setCollapsed(next)
  }

  // 훅이라 로딩·에러 조기 반환보다 위에 있어야 한다(호출 순서가 렌더마다 같아야 한다).
  const paged = usePaged(filtered, PAGE_SIZE)

  if (loading) return <Loader label="기술 블로그 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="tech_blogs.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python -m crawlers.crawl_techblog_graph</code> (catch_capture)</>}
      />
    )

  // 글을 고르면 목록을 통째로 갈아끼운다 — 공고 상세와 같은 방식이다. 모달로 띄우면
  // 남의 기술 글이 어두운 장막 뒤 좁은 칸에 갇혀 코드 블록과 그림이 가로로 넘친다.
  // key 를 글 주소로 두면 추천을 눌러 다른 글로 넘어갈 때 스크롤·번역 토글이 초기화된다.
  if (selected)
    return (
      <BlogDetail
        key={selected.url}
        post={selected}
        onClose={() => goBack(paths.blog())}
        onOpenUrl={(url) => {
          // 추천 JSON 은 url 만 들고 있다. 필터에 걸려 목록에 없는 글도 열려야 하므로
          // 필터된 목록이 아니라 posts 전체에서 찾는다.
          const next = posts.find((p) => p.url === url)
          if (next) openPost(next)
        }}
      />
    )

  return (
    <div className="flex flex-1 min-h-0 min-w-0">
      {/* 사이드바: 검색 + 국가 + 카테고리별 기술 키워드 (모바일=드로어) */}
      <SidePanel side="left" desktopWidth="md:w-80" open={navOpen} onClose={() => setNavOpen(false)}>
       <div className="overflow-auto p-4 flex flex-col gap-4">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="키워드 검색 (제목·요약·기술)"
          className="w-full px-3 py-2 text-sm rounded bg-(--color-bg) border border-(--color-border) text-(--color-text) placeholder:text-(--color-muted)"
        />

        <div>
          <div className="text-xs text-(--color-muted) mb-2">국가</div>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={country === null} onClick={() => setCountry(null)}>
              전체
            </Chip>
            {countries.map(([c, n]) => (
              <Chip key={c} active={country === c} onClick={() => setCountry(country === c ? null : c)}>
                {COUNTRY_LABEL[c] ?? c} {n}
              </Chip>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-(--color-muted)">
          <span>기술 키워드 (카테고리별)</span>
          {stacks.size > 0 && (
            <button onClick={() => setStacks(new Set())} className="text-(--color-accent) hover:underline">
              선택 초기화 ({stacks.size})
            </button>
          )}
        </div>
        <div className="flex flex-col gap-2 -mt-2">
          {grouped.map(([cat, tags]) => {
            const isCollapsed = collapsed.has(cat)
            return (
              <div key={cat}>
                <button
                  onClick={() => toggleCat(cat)}
                  className="w-full flex items-center gap-1 text-xs font-medium text-(--color-text) py-1 hover:text-(--color-accent)"
                >
                  <span className="text-(--color-muted)">{isCollapsed ? '▸' : '▾'}</span>
                  {cat}
                  <span className="text-(--color-muted) font-normal">({tags.length})</span>
                </button>
                {!isCollapsed && (
                  <div className="flex flex-wrap gap-1.5 pl-3 pb-1">
                    {tags.map(([name, n]) => (
                      <Chip key={name} active={stacks.has(name)} onClick={() => toggleStack(name)}>
                        <TechIcon tech={name} size={13} />
                        {name} <span className="opacity-60">{n}</span>
                      </Chip>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
       </div>
      </SidePanel>

      {/* 본문: 글 목록 */}
      <main data-scroll className="flex-1 min-w-0 overflow-auto">
        <MobileBar onMenu={() => setNavOpen(true)} label="검색·필터">
          <span className="ml-auto text-xs text-(--color-muted)">{filtered.length}건</span>
        </MobileBar>
        <div className="px-5 py-3 border-b border-(--color-border) text-xs text-(--color-muted) flex items-center gap-3">
          <span>
            {data?.total ?? 0}건 중 <b className="text-(--color-text)">{filtered.length}건</b>
            {' · '}
            {countries.length}개국 · {data?.sources.length ?? 0}개 블로그
          </span>
          {data?.generated_at && <span className="ml-auto">갱신 {data.generated_at.slice(0, 10)}</span>}
        </div>
        <ul className="divide-y divide-(--color-border)">
          {paged.slice.map((p) => (
            <PostRow key={p.url} post={p} onPickStack={toggleStack} onOpen={openPost} />
          ))}
          {filtered.length === 0 && (
            <li className="p-8 text-(--color-muted)">조건에 맞는 글이 없습니다.</li>
          )}
        </ul>
        {filtered.length > 0 && (
          <Pagination
            page={paged.page}
            totalPages={paged.totalPages}
            total={filtered.length}
            pageSize={PAGE_SIZE}
            onChange={paged.setPage}
          />
        )}
      </main>

    </div>
  )
}

function PostRow({
  post,
  onPickStack,
  onOpen,
}: {
  post: BlogPost
  onPickStack: (s: string) => void
  onOpen: (p: BlogPost) => void
}) {
  return (
    <li className="px-4 sm:px-5 py-4 min-w-0 hover:bg-(--color-panel) transition">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-(--color-muted) mb-1">
        <span className="inline-flex items-center gap-1.5">
          <CompanyMark name={post.company} size={15} />
          <span className="text-(--color-accent) font-medium">{post.company}</span>
        </span>
        <span>{COUNTRY_LABEL[post.country] ?? post.country}</span>
        {post.published && <span>· {post.published}</span>}
        {post.lang && post.lang !== 'ko' && (
          <span className="px-1.5 rounded bg-(--color-bg) border border-(--color-border)">번역</span>
        )}
        {post.categories.length > 0 && (
          <span className="sm:ml-auto text-(--color-muted) break-words">{post.categories.join(' · ')}</span>
        )}
      </div>
      <a
        href={paths.blogPost(blogKey(post))}
        onClick={(e) => {
          if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
          e.preventDefault()
          onOpen(post)
        }}
        className="block text-left text-(--color-text) font-medium break-words hover:text-(--color-accent) hover:underline"
      >
        {post.title}
      </a>
      <a
        href={post.url}
        target="_blank"
        rel="noreferrer"
        className="ml-2 text-xs text-(--color-muted) hover:text-(--color-accent)"
      >
        ↗
      </a>
      {post.summary && (
        <p className="mt-1 text-sm text-(--color-muted) line-clamp-2">{post.summary}</p>
      )}
      {post.tech_stack.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {post.tech_stack.map((t) => (
            <button
              key={t}
              onClick={() => onPickStack(t)}
              className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-(--color-bg) border border-(--color-border) text-(--color-muted) hover:border-(--color-accent) hover:text-(--color-accent)"
            >
              <TechIcon tech={t} size={13} />
              {t}
            </button>
          ))}
        </div>
      )}
    </li>
  )
}

function Chip({
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
      className={`inline-flex items-center gap-1 px-2 py-1 text-xs rounded transition border ${
        active
          ? 'bg-(--color-accent) text-(--color-on-accent) border-(--color-accent) font-medium'
          : 'bg-(--color-bg) text-(--color-text) border-(--color-border) hover:border-(--color-accent)'
      }`}
    >
      {children}
    </button>
  )
}
