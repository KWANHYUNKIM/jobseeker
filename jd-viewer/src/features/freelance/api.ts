import { apiOrFile } from '../../api/client'
import type { FreelanceData } from './utils/freelance'

/**
 * 외주·프리 프로젝트 전량과 단가 분석. 뷰어 API(`/api/freelance`)가 먼저다 — 프로젝트의
 * 모집 상태를 DB 가 읽는 순간 계산한다. 없으면 크롤 단계가 구운 freelance.json.
 */
export async function fetchFreelance(): Promise<FreelanceData> {
  return (await apiOrFile<FreelanceData>('/api/freelance', '/freelance.json')).data
}
