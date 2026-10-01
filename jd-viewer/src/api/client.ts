/**
 * 공통 요청 설정 — 뷰어 API(backend, 8771)와 정적 파일.
 *
 * 화면 데이터는 **API 가 먼저, 안 되면 정적 파일**이다. API 는 정본 DB 를 읽는 순간의
 * 상태를 주고(마감·추천이 늦지 않다), 파일은 크롤 사이클마다 구운 사본이라 사전
 * 렌더링과 API 가 없는 배포(정적 호스팅·DB 가 내려간 동안)를 위해 남아 있다.
 */

// 개발 중에는 뷰어(5173)와 API(8771)가 다른 포트다. 배포에서는 nginx 가 /api 를
// 같은 오리진으로 프록시하므로 상대 경로면 된다.
export const API_BASE = import.meta.env.DEV ? 'http://127.0.0.1:8771' : ''

export class HttpError extends Error {
  readonly status: number
  constructor(status: number, url: string) {
    super(`HTTP ${status} (${url})`)
    this.status = status
  }
}

/**
 * JSON 을 받는다. 상태 코드만 믿지 않는다 — /api/ 프록시가 없는 배포(와 vite 개발
 * 서버)에서는 없는 경로에 SPA 폴백(index.html)이 200 으로 온다. 그걸 JSON 으로 읽다
 * 깨지는 대신 404 로 취급한다.
 */
export async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  const isJson = (r.headers.get('content-type') ?? '').includes('json')
  if (r.ok && !isJson) throw new HttpError(404, url)
  if (!r.ok) throw new HttpError(r.status, url)
  return (await r.json()) as T
}

/** 뷰어 API 의 경로(`/api/...`)를 부른다. */
export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return getJson<T>(`${API_BASE}${path}`, init)
}

export type Source = 'api' | 'file'

/**
 * API 를 먼저 부르고, 실패하면(없는 경로·DB 다운 503·네트워크) 같은 모양의 정적 파일을
 * 받는다. 어느 쪽에서 왔는지도 돌려준다 — 화면이 "몇 시 기준" 을 다르게 말할 수 있다.
 */
export async function apiOrFile<T>(
  apiPath: string,
  filePath: string,
  init?: RequestInit,
): Promise<{ data: T; source: Source }> {
  try {
    return { data: await apiGet<T>(apiPath, init), source: 'api' }
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    return { data: await getJson<T>(filePath, init), source: 'file' }
  }
}

/**
 * 정적 문서(역설계·브리핑·도서·트렌드·캘린더·마인드맵 …)를 받는다 — `fetch(path)` 자리에 그대로 쓴다.
 *
 * 뷰어 API 의 `/api/docs/<경로>` 가 먼저다(파이프라인이 DB 에 옮겨 둔 같은 내용). 없거나(404),
 * API 가 안 되거나, SPA 폴백(index.html)이 오면 원래 정적 파일을 받는다. 돌려주는 건 Response 라
 * 호출부의 처리(ok·json·text)는 바꿀 필요가 없다.
 */
export async function docFetch(path: string, init?: RequestInit): Promise<Response> {
  const rel = path.replace(/^\//, '').split('/').map(encodeURIComponent).join('/')
  try {
    const r = await fetch(`${API_BASE}/api/docs/${rel}`, init)
    const type = r.headers.get('content-type') ?? ''
    if (r.ok && (type.includes('json') || type.includes('markdown'))) return r
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
  }
  return fetch(path, init)
}
