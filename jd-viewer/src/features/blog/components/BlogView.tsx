import { useMemo, useState, type ReactNode } from 'react'
import { useBlogs } from '../hooks/useBlogs'
import { usePaged, PAGE_SIZE_DENSE as PAGE_SIZE } from '../../../hooks/usePaged'
import { BlogDetail } from './BlogDetail'
import { goBack, navigate } from '../../../utils/navigation'
import { blogKey, paths } from '../../../utils/urls'
import { absUrl, clip, useSeo } from '../../../utils/seo'
import { Loader, ErrorState, CompanyMark } from '../../../components/ui'
import { Pager } from '../../../components/Pager'
import { SiteFooter } from '../../../components/SiteFooter'
import type { BlogPost } from '../../../types'

const COUNTRY: Record<string, string> = { KR: '국내', US: '미국', JP: '일본', DE: '독일', GB: '영국', IN: '인도', SG: '싱가포르' }
const PICK_BG = ['#fff1e8', '#eef3ff', '#eaf7f0']
const TAB_COUNT = 11 // 위 탭에 놓는 카테고리 수 — 나머지는 오른쪽 '카테고리' 칸에서 고른다
const CHIP_COUNT = 15 // 회사 칩 두 줄

/**
 * 기술 블로그(캐치형 05) — 제목·검색, 회사 칩(글 수 순), 카테고리 탭, '오늘 올라온 주목할 글' 세 장,
 * 그 아래 왼쪽은 새 글 목록(쪽 번호), 오른쪽은 글이 많은 회사 TOP 10 · 카테고리 · 내 스택에 맞는 글만 보기.
 * 글을 고르면(/blog/<id>) 목록 대신 글 상세가 뜬다.
 */
export function BlogView({ postId }: { postId?: string | null }) {
  const { data, loading, error } = useBlogs()
  const [query, setQuery] = useState('')
  // ?company=AWS 로 들어오면 그 회사 글만 고른 채로 연다(글 상세의 '이 회사 글 전체 보기').
  const [company, setCompany] = useState<string | null>(() => new URLSearchParams(window.location.search).get('company'))
  const [cat, setCat] = useState<string | null>(null)
  const [stacks, setStacks] = useState<Set<string>>(new Set())
  const [oldest, setOldest] = useState(false)
  const [allChips, setAllChips] = useState(false)

  // 매 렌더마다 새 배열이 되면 아래 useMemo 들이 전부 다시 돈다(글 1천여 건 × 필터).
  const posts = useMemo(() => data?.posts ?? [], [data])
  // 열려 있는 글은 주소(/blog/<id>)에서 나온다 — 글 하나하나가 공유 가능한 링크가 된다.
  const selected = useMemo(() => (postId ? (posts.find((p) => blogKey(p) === postId) ?? null) : null), [posts, postId])
  const openPost = (p: BlogPost) => navigate(paths.blogPost(blogKey(p)))

  // 글 상세는 남의 글을 옮겨 놓은 화면이다. 주소는 있어야 하지만 색인은 원문이 가져가는 게 맞다.
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
  const cats = data?.categories ?? []

  const companies = useMemo(() => {
    const c = new Map<string, { n: number; country: string }>()
    for (const p of posts) c.set(p.company, { n: (c.get(p.company)?.n ?? 0) + 1, country: p.country })
    return [...c].map(([name, v]) => ({ name, ...v })).sort((a, b) => b.n - a.n || (a.name < b.name ? -1 : 1))
  }, [posts])
  const domestic = companies.filter((c) => c.country === 'KR').length

  const stackCount = useMemo(() => {
    const c = new Map<string, number>()
    for (const p of posts) for (const t of p.tech_stack) c.set(t, (c.get(t) ?? 0) + 1)
    return [...c].sort((a, b) => b[1] - a[1])
  }, [posts])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const out = posts.filter((p) => {
      if (company && p.company !== company) return false
      if (cat && !p.categories.includes(cat)) return false
      if (stacks.size && !p.tech_stack.some((t) => stacks.has(t))) return false
      if (q && !`${p.title} ${p.summary} ${p.company} ${p.tags.join(' ')} ${p.tech_stack.join(' ')}`.toLowerCase().includes(q)) return false
      return true
    })
    return [...out].sort((a, b) => (oldest ? a.published_ts - b.published_ts : b.published_ts - a.published_ts))
  }, [posts, query, company, cat, stacks, oldest])

  // 주목할 글 — 지금 조건에서 가장 새 글 셋, 회사가 겹치지 않게.
  const picks = useMemo(() => {
    const out: BlogPost[] = []
    for (const p of [...filtered].sort((a, b) => b.published_ts - a.published_ts)) {
      if (out.some((o) => o.company === p.company)) continue
      out.push(p)
      if (out.length === 3) break
    }
    return out
  }, [filtered])

  // 새 글 목록 — 위 주목할 글 세 장은 빼고 늘어놓는다(같은 글이 두 번 보이지 않게).
  const rest = useMemo(() => filtered.filter((p) => !picks.includes(p)), [filtered, picks])
  // 훅이라 로딩·에러 조기 반환보다 위에 있어야 한다(호출 순서가 렌더마다 같아야 한다).
  const paged = usePaged(rest, PAGE_SIZE)

  if (loading) return <Loader label="기술 블로그 불러오는 중…" />
  if (error)
    return (
      <ErrorState
        title="tech_blogs.json 로드 실패"
        detail={error}
        hint={<>생성: <code className="text-(--color-text)">python -m crawlers.crawl_techblog_graph</code> (catch_capture)</>}
      />
    )

  // 글을 고르면 목록을 통째로 갈아끼운다 — 공고 상세와 같은 방식이다.
  if (selected)
    return (
      <BlogDetail
        key={selected.url}
        post={selected}
        allPosts={posts}
        onClose={() => goBack(paths.blog())}
        onOpenUrl={(url) => {
          // 추천 JSON 은 url 만 들고 있다. 필터에 걸려 목록에 없는 글도 열려야 하므로 posts 전체에서 찾는다.
          const next = posts.find((p) => p.url === url)
          if (next) openPost(next)
        }}
      />
    )

  const toggleStack = (name: string) => {
    const next = new Set(stacks)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setStacks(next)
  }

  return (
    <div data-scroll className="flex-1 min-h-0 overflow-auto bg-white">
      <div className="jd-container pt-[43px] pb-[90px]">
        <h1 className="text-[28px] font-bold leading-10 tracking-[-0.6px] text-[#272727]">기술 블로그</h1>
        <p className="mt-1 text-base leading-6 tracking-[-0.16px] text-[#666]">
          국내외 <b className="font-bold text-(--color-accent)">{companies.length}개 회사</b>의 개발 블로그 새 글 {posts.length.toLocaleString()}개를 매일
          모아요. 국내 {domestic}곳 · 해외 {companies.length - domestic}곳
        </p>

        <form role="search" onSubmit={(e) => e.preventDefault()} className="mt-[23px] flex gap-2.5">
          <label className="flex-1 min-w-0 flex items-center gap-2.5 h-[52px] rounded-[26px] border border-[#c4c4c4] pl-[23px] pr-5 focus-within:border-[#272727]">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#272727" strokeWidth="2" aria-hidden className="shrink-0">
              <circle cx="8.5" cy="8.5" r="5.5" />
              <path d="M12.5 12.5 16 16" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="제목·회사·기술 태그로 찾아보세요"
              aria-label="글 검색"
              className="flex-1 min-w-0 bg-transparent text-[15px] tracking-[-0.16px] text-[#272727] placeholder:text-[#999] outline-none"
            />
          </label>
          <button type="submit" className="shrink-0 w-[110px] h-[52px] rounded-[26px] border-2 border-(--color-accent) text-base font-bold text-(--color-accent) hover:bg-(--color-accent-weak)">
            검색
          </button>
        </form>

        {/* 회사 칩 — 글 수 순 */}
        <div className="mt-[22px] flex flex-wrap gap-2">
          {(allChips ? companies : companies.slice(0, CHIP_COUNT)).map((c) => {
            const on = company === c.name
            return (
              <button
                key={c.name}
                type="button"
                aria-pressed={on}
                onClick={() => setCompany(on ? null : c.name)}
                className={
                  'inline-flex items-center gap-2 h-[52px] pl-[7px] pr-4 rounded-[26px] border ' +
                  (on ? 'bg-(--color-accent-weak) border-(--color-accent)' : 'bg-white border-[#e2e8ec] hover:border-[#999]')
                }
              >
                <span className="grid place-items-center w-10 h-10 rounded-xl overflow-hidden">
                  <CompanyMark name={c.name} size={40} />
                </span>
                <span className={'text-sm font-medium tracking-[-0.16px] ' + (on ? 'text-(--color-accent)' : 'text-[#272727]')}>{c.name}</span>
                <span className="text-xs text-[#999] tabular-nums">{c.n}</span>
              </button>
            )
          })}
          {companies.length > CHIP_COUNT && (
            <button type="button" onClick={() => setAllChips((v) => !v)} className="h-[52px] px-4 text-sm text-[#777] hover:text-[#272727]">
              {allChips ? '접기' : `+${companies.length - CHIP_COUNT}곳 더`}
            </button>
          )}
        </div>

        {/* 카테고리 탭 */}
        <div role="tablist" className="mt-[34px] flex overflow-x-auto no-scrollbar border-b border-[#e2e2e2]">
          {[null, ...cats.slice(0, TAB_COUNT)].map((c) => (
            <button
              key={c ?? 'all'}
              type="button"
              role="tab"
              aria-selected={cat === c}
              onClick={() => setCat(c)}
              className={
                'relative shrink-0 px-4 pb-[13px] text-base leading-6 tracking-[-0.16px] ' +
                (cat === c ? 'font-bold text-(--color-accent) after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-(--color-accent)' : 'font-medium text-[#777] hover:text-[#272727]')
              }
            >
              {c ?? '전체'}
            </button>
          ))}
        </div>

        {/* 오늘 올라온 주목할 글 */}
        {picks.length > 0 && (
          <section className="mt-[43px]">
            <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">
              오늘 올라온 <span className="font-black text-(--color-accent)">주목할 글</span>
            </h2>
            <div className="mt-5 grid md:grid-cols-3 gap-4">
              {picks.map((p, i) => (
                <a
                  key={p.url}
                  href={paths.blogPost(blogKey(p))}
                  onClick={(e) => {
                    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
                    e.preventDefault()
                    openPost(p)
                  }}
                  className="home-press block h-[300px] rounded-3xl px-7 pt-[27px] overflow-hidden"
                  style={{ background: PICK_BG[i % 3] }}
                >
                  <span className="flex items-center gap-3">
                    <span className="grid place-items-center w-11 h-11 rounded-xl overflow-hidden shrink-0">
                      <CompanyMark name={p.company} size={44} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-base font-bold leading-6 text-[#272727] truncate">{p.company}</span>
                      <span className="block text-[13px] leading-[19px] text-[#777]">
                        {COUNTRY[p.country] ?? p.country} · {p.published}
                      </span>
                    </span>
                  </span>
                  <span className="mt-[21px] line-clamp-2 text-[22px] font-bold leading-[31px] tracking-[-0.4px] text-[#272727]">{p.title}</span>
                  <span className="mt-[10px] line-clamp-3 text-[15px] leading-[22px] tracking-[-0.16px] text-[#474747]">{p.summary}</span>
                  <span className="mt-[23px] flex flex-wrap gap-1.5 h-[22px] overflow-hidden">
                    {tagsOf(p).slice(0, 2).map((t) => (
                      <span key={t} className="rounded bg-white/75 px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-[#474747]">
                        #{t}
                      </span>
                    ))}
                  </span>
                </a>
              ))}
            </div>
          </section>
        )}

        <div className="mt-[50px] flex flex-col lg:flex-row gap-7 items-start">
          {/* 새 글 */}
          <section data-blog-top className="flex-1 min-w-0 w-full scroll-mt-4">
            <div className="flex items-center justify-between">
              <h2 className="text-[22px] font-bold leading-8 tracking-[-0.22px] text-[#272727]">새 글</h2>
              <label className="relative inline-flex items-center h-9 rounded-md border border-[#d8d8d8] bg-white">
                <select
                  aria-label="정렬"
                  value={oldest ? 'old' : 'new'}
                  onChange={(e) => setOldest(e.target.value === 'old')}
                  className="appearance-none h-full bg-transparent pl-[15px] pr-[33px] text-sm tracking-[-0.16px] text-[#272727] outline-none cursor-pointer"
                >
                  <option value="new">최신순</option>
                  <option value="old">오래된순</option>
                </select>
                <svg className="pointer-events-none absolute right-[14px]" width="10" height="8" viewBox="0 0 10 8" fill="none" stroke="#272727" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
                  <path d="M1.5 2.5 5 6l3.5-3.5" />
                </svg>
              </label>
            </div>
            <ul className="mt-[14px] border-t-2 border-[#272727]">
              {paged.slice.map((p) => (
                <PostRow key={p.url} post={p} onOpen={openPost} />
              ))}
              {rest.length === 0 && <li className="py-16 text-center text-sm text-[#999]">조건에 맞는 글이 없어요.</li>}
            </ul>
            <Pager page={paged.page} totalPages={paged.totalPages} onChange={paged.setPage} scrollTo="[data-blog-top]" />
          </section>

          {/* 오른쪽 칸 */}
          <aside className="w-full lg:w-[348px] shrink-0 flex flex-col gap-4">
            <Box>
              <h3 className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">
                글이 많은 회사 <span className="font-black text-(--color-accent)">TOP 10</span>
              </h3>
              <ol className="mt-[18px] flex flex-col gap-3">
                {companies.slice(0, 10).map((c, i) => (
                  <li key={c.name}>
                    <button type="button" onClick={() => setCompany(company === c.name ? null : c.name)} className="w-full flex items-center gap-3 text-left">
                      <span className={'w-[18px] text-center text-[15px] font-bold tabular-nums ' + (i < 3 ? 'text-(--color-accent)' : 'text-[#777]')}>{i + 1}</span>
                      <span className="grid place-items-center w-7 h-7 rounded-lg overflow-hidden shrink-0">
                        <CompanyMark name={c.name} size={28} />
                      </span>
                      <span className={'flex-1 min-w-0 truncate text-[15px] ' + (company === c.name ? 'font-bold text-(--color-accent)' : 'text-[#272727]')}>{c.name}</span>
                      <span className="text-[13px] text-[#999] tabular-nums">{c.n}개</span>
                    </button>
                  </li>
                ))}
              </ol>
            </Box>
            <Box>
              <h3 className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">카테고리</h3>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {cats.map((c) => (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={cat === c}
                    onClick={() => setCat(cat === c ? null : c)}
                    className={'rounded px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] ' + (cat === c ? 'bg-(--color-accent) text-white' : 'bg-[#f4f4f4] text-[#474747] hover:bg-[#eaeaea]')}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </Box>
            <StackBox stacks={stacks} top={stackCount.slice(0, 30)} onToggle={toggleStack} onClear={() => setStacks(new Set())} />
          </aside>
        </div>
      </div>
      <SiteFooter updated={data?.generated_at} />
    </div>
  )
}

// 블로그 엔진이 기본으로 붙여 두는 빈 태그('hello world' 등)는 뜻이 없어서 뺀다.
const JUNK_TAGS = new Set(['hello world', 'uncategorized', '미분류'])
const tagsOf = (p: BlogPost) => p.tags.filter((t) => !JUNK_TAGS.has(t.trim().toLowerCase()))

function Box({ children }: { children: ReactNode }) {
  return <div className="rounded-[22px] border border-[#e2e8ec] bg-white px-[23px] pt-[23px] pb-[22px]">{children}</div>
}

/** 내 스택에 맞는 글만 보기 — 단추를 누르면 많이 쓰인 기술 30개가 펼쳐지고, 고른 기술 태그가 붙은 글만 남긴다. */
function StackBox({
  stacks,
  top,
  onToggle,
  onClear,
}: {
  stacks: Set<string>
  top: [string, number][]
  onToggle: (t: string) => void
  onClear: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-[22px] bg-[#f3f6f8] px-[22px] pt-[22px] pb-[22px]">
      <h3 className="text-[17px] font-bold leading-[25px] tracking-[-0.16px] text-[#272727]">내 스택에 맞는 글만 보기</h3>
      <p className="mt-2 text-sm leading-[21px] tracking-[-0.16px] text-[#666]">관심 기술을 고르면 그 기술 태그가 붙은 글만 모아서 보여드려요.</p>
      {open && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {top.map(([t, n]) => (
            <button
              key={t}
              type="button"
              aria-pressed={stacks.has(t)}
              onClick={() => onToggle(t)}
              className={'h-7 px-2.5 rounded-full border text-xs ' + (stacks.has(t) ? 'bg-(--color-accent) border-(--color-accent) text-white' : 'bg-white border-[#e2e2e2] text-[#474747]')}
            >
              {t} <span className={stacks.has(t) ? 'text-[#ffd9d9]' : 'text-[#999]'}>{n}</span>
            </button>
          ))}
        </div>
      )}
      <button
        type="button"
        onClick={() => (open && stacks.size ? onClear() : setOpen((v) => !v))}
        className="mt-[15px] w-full h-11 rounded-md bg-(--color-accent) text-[15px] font-bold text-white hover:bg-(--color-accent-deep)"
      >
        {!open ? '관심 기술 설정하기' : stacks.size ? `선택 풀기 (${stacks.size})` : '닫기'}
      </button>
    </div>
  )
}

function PostRow({ post, onOpen }: { post: BlogPost; onOpen: (p: BlogPost) => void }) {
  const to = paths.blogPost(blogKey(post))
  return (
    <li className="relative border-b border-[#e8ecef] py-[26px] pl-[6px] pr-8">
      <div className="flex gap-[18px]">
        <span className="grid place-items-center w-[52px] h-[52px] rounded-[14px] overflow-hidden shrink-0">
          <CompanyMark name={post.company} size={52} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap gap-x-[18px] text-sm leading-[21px] tracking-[-0.16px] text-[#777]">
            <span>{post.company}</span>
            <span>{post.country === 'KR' ? '국내' : (COUNTRY[post.country] ?? post.country)}</span>
            <span className="tabular-nums">{post.published}</span>
          </div>
          <a
            href={to}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return
              e.preventDefault()
              onOpen(post)
            }}
            className="mt-[5px] block text-[19px] font-bold leading-[27px] tracking-[-0.3px] text-[#272727] truncate hover:underline underline-offset-2"
          >
            {post.title}
          </a>
          {post.summary && <p className="mt-1.5 line-clamp-2 text-[15px] leading-[22px] tracking-[-0.16px] text-[#666]">{post.summary}</p>}
          {tagsOf(post).length > 0 && (
            <div className="mt-[10px] flex flex-wrap gap-1.5">
              {tagsOf(post).slice(0, 3).map((t) => (
                <span key={t} className="rounded bg-[#f4f4f4] px-[7px] text-[13px] leading-[22px] tracking-[-0.13px] text-[#474747]">
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <a href={post.url} target="_blank" rel="noreferrer" aria-label="원문 새 창으로 열기" className="absolute right-[6px] top-[37px] text-[#bbb] hover:text-[#272727]">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
          <path d="M5 2H2v8h8V7M7 1.5h3.5V5M10.5 1.5 5.5 6.5" />
        </svg>
      </a>
    </li>
  )
}
