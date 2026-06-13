import { useEffect, useState } from 'react'

// build_learning.py 가 만드는 learning_resources.json 의 영상 1건
export type LearningStage = '입문' | '핵심' | '실전'

export interface LearningVideo {
  title: string
  url: string
  thumbnail: string
  channel: string
  views: number
  length: string
  published: string
  stage: LearningStage
}

export interface CurriculumTopic {
  topic: string
  note: string
  videos: LearningVideo[]
}

export interface Curriculum {
  guide: string
  topics: CurriculumTopic[]
}

interface LearningFile {
  generated_at: string
  source: string
  tech_count: number
  search_url: string // "...search_query={tech}+강의"
  resources: Record<string, LearningVideo[]>
  curricula?: Record<string, Curriculum>
}

interface State {
  resources: Record<string, LearningVideo[]>
  curricula: Record<string, Curriculum>
  searchUrl: string
  source: string
  loading: boolean
  error: string | null
}

export function useLearning(): State {
  const [state, setState] = useState<State>({
    resources: {},
    curricula: {},
    searchUrl: '',
    source: '',
    loading: true,
    error: null,
  })

  useEffect(() => {
    let cancelled = false
    fetch('/learning_resources.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data: LearningFile) => {
        if (cancelled) return
        setState({
          resources: data.resources ?? {},
          curricula: data.curricula ?? {},
          searchUrl: data.search_url ?? '',
          source: data.source ?? '',
          loading: false,
          error: null,
        })
      })
      .catch((e) => {
        if (!cancelled)
          setState({
            resources: {},
            curricula: {},
            searchUrl: '',
            source: '',
            loading: false,
            error: String(e),
          })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
