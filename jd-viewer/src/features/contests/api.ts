import { docFetch } from '../../api/client'
import type { ContestsData } from './utils/contests'

/**
 * IT·디자인 공모전 전량. 크롤 단계가 구운 contests.json 을 문서 API(`/api/docs/contests.json`)로 먼저,
 * 안 되면 정적 파일로 읽는다.
 */
export async function fetchContests(init?: RequestInit): Promise<ContestsData> {
  const r = await docFetch('/contests.json', init)
  if (!r.ok) throw new Error(`contests.json ${r.status}`)
  return (await r.json()) as ContestsData
}
