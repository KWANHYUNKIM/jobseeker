import { apiOrFile } from '../../api/client'
import type { BlogFile } from '../../types'

/** 글 목록. 뷰어 API(`/api/posts`)가 먼저, 없으면 크롤러가 구운 tech_blogs.json. */
export async function fetchBlogs(): Promise<BlogFile> {
  return (await apiOrFile<BlogFile>('/api/posts', '/tech_blogs.json')).data
}
