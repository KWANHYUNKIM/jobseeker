import { apiGet, apiOrFile } from '../../api/client'
import type { FreelanceData, ProjectDetail } from './utils/freelance'

/**
 * 외주·프리 프로젝트 전량과 단가 분석. 뷰어 API(`/api/freelance`)가 먼저다 — 프로젝트의
 * 모집 상태를 DB 가 읽는 순간 계산한다. 없으면 크롤 단계가 구운 freelance.json.
 */
export async function fetchFreelance(): Promise<FreelanceData> {
  return (await apiOrFile<FreelanceData>('/api/freelance', '/freelance.json')).data
}

/**
 * 프로젝트 한 건과 상세 본문(크롤러가 받아 DB project_body 에 둔 것, 연락처는 지웠다).
 * 정적 파일 폴백이 없다 — API 가 안 되면 호출부가 목록 데이터(요약)로 물러선다.
 */
export function fetchFreelanceProject(site: string, pid: string, init?: RequestInit): Promise<ProjectDetail> {
  return apiGet<ProjectDetail>(`/api/freelance/projects/${encodeURIComponent(site)}/${encodeURIComponent(pid)}`, init)
}
