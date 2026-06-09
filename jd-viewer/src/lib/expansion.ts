// 기술스택 확장 분석
// company_stacks.json(이미 로드된 CompanyStack[])에서 클라이언트 계산:
//  1) 기술 → 회사 역인덱스 (어떤 회사가 이 기술을 쓰나)
//  2) 기술 동시출현 (회사 단위) — confidence/lift 로 "확장 추천" 산출
//  3) 카테고리/기술 메타 (선택 UI 용)
// 정적: 직군별 큐레이션 로드맵.

import type { CompanyStack } from '../types'

export const CAT_ORDER = [
  '언어',
  '백엔드',
  '프론트엔드',
  '모바일',
  '데이터베이스',
  '인프라/DevOps',
  '펌웨어/임베디드',
  'AI/ML',
  '데이터',
  '협업/도구',
  '기타',
]

export const CAT_COLOR: Record<string, string> = {
  언어: '#c084fc',
  백엔드: '#60a5fa',
  프론트엔드: '#34d399',
  모바일: '#fbbf24',
  데이터베이스: '#22d3ee',
  '인프라/DevOps': '#fb923c',
  '펌웨어/임베디드': '#a78bfa',
  'AI/ML': '#f472b6',
  데이터: '#2dd4bf',
  '협업/도구': '#94a3b8',
  기타: '#6b7280',
}

export interface TechNode {
  name: string
  category: string
  companyCount: number // 이 기술을 쓰는 회사 수
  postingCount: number // 공고 누적(회사별 count 합)
}

export interface CompanyRef {
  name: string
  norm: string
  size: string
  count: number // 이 회사에서 해당 기술 공고 수
  domains: string[]
}

export interface CoocItem {
  name: string
  category: string
  coCount: number // 두 기술을 함께 쓰는 회사 수
  confidence: number // P(b|a) = coCount / count(a)
  lift: number // confidence / P(b)
}

export interface ExpansionIndex {
  techs: TechNode[] // companyCount 내림차순
  byCategory: Record<string, TechNode[]>
  companiesByTech: Record<string, CompanyRef[]> // key = tech name
  coocByTech: Record<string, CoocItem[]> // key = tech name, lift 내림차순
  categoryOf: Record<string, string>
  totalCompanies: number
}

const MIN_SUPPORT = 3 // 동시출현 최소 회사 수 (노이즈 컷)
const MIN_LIFT = 1.2 // 연관도 하한 — 어디서나 쓰이는 기술(lift≈1) 제거

export function buildExpansionIndex(companies: CompanyStack[]): ExpansionIndex {
  const total = companies.length
  const categoryOf: Record<string, string> = {}
  const companyCount: Record<string, number> = {}
  const postingCount: Record<string, number> = {}
  const companiesByTech: Record<string, CompanyRef[]> = {}
  // 회사 단위 동시출현: cooc[a][b] = 두 기술 모두 쓰는 회사 수
  const cooc: Record<string, Record<string, number>> = {}

  for (const c of companies) {
    // 회사가 가진 (기술, count) 모음 — 같은 기술이 여러 카테고리에 있진 않지만 방어적으로 합산
    const techCount: Record<string, number> = {}
    for (const cat of Object.keys(c.tech_categories)) {
      for (const t of c.tech_categories[cat]) {
        if (!(t.name in categoryOf)) categoryOf[t.name] = cat
        techCount[t.name] = (techCount[t.name] ?? 0) + t.count
      }
    }
    const names = Object.keys(techCount)
    const domains = c.domains.map((d) => d.name)
    for (const name of names) {
      companyCount[name] = (companyCount[name] ?? 0) + 1
      postingCount[name] = (postingCount[name] ?? 0) + techCount[name]
      ;(companiesByTech[name] ??= []).push({
        name: c.name,
        norm: c.norm,
        size: c.size,
        count: techCount[name],
        domains,
      })
    }
    // 동시출현 (정렬 불필요, 양방향 기록)
    for (let i = 0; i < names.length; i++) {
      const a = names[i]
      const ra = (cooc[a] ??= {})
      for (let j = 0; j < names.length; j++) {
        if (i === j) continue
        const b = names[j]
        ra[b] = (ra[b] ?? 0) + 1
      }
    }
  }

  const techs: TechNode[] = Object.keys(companyCount).map((name) => ({
    name,
    category: categoryOf[name] ?? '기타',
    companyCount: companyCount[name],
    postingCount: postingCount[name],
  }))
  techs.sort((x, y) => y.companyCount - x.companyCount || y.postingCount - x.postingCount)

  const byCategory: Record<string, TechNode[]> = {}
  for (const t of techs) (byCategory[t.category] ??= []).push(t)

  // 회사 목록은 공고수 내림차순
  for (const k of Object.keys(companiesByTech)) {
    companiesByTech[k].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }

  // 동시출현 → 확장 추천: lift 로 "유난히 함께 쓰는" 기술 우선, 최소 지지 회사수 컷
  const coocByTech: Record<string, CoocItem[]> = {}
  for (const a of Object.keys(cooc)) {
    const baseA = companyCount[a]
    const items: CoocItem[] = []
    for (const b of Object.keys(cooc[a])) {
      const co = cooc[a][b]
      if (co < MIN_SUPPORT) continue
      const conf = co / baseA
      const pB = companyCount[b] / total
      const lift = pB > 0 ? conf / pB : 0
      if (lift < MIN_LIFT) continue
      items.push({ name: b, category: categoryOf[b] ?? '기타', coCount: co, confidence: conf, lift })
    }
    // 동반율(confidence) 우선 — 실속 있는 추천. 동률이면 동반 회사수
    items.sort((x, y) => y.confidence - x.confidence || y.coCount - x.coCount)
    coocByTech[a] = items
  }

  return { techs, byCategory, companiesByTech, coocByTech, categoryOf, totalCompanies: total }
}

// ── 직군별 큐레이션 로드맵 ────────────────────────────────────────────────
// 각 step 의 techs 는 expansion 인덱스의 canonical 이름과 맞춰, 데이터 존재 여부를
// 매칭해 회사수 배지를 붙인다.
export interface RoadmapStep {
  tier: string
  note: string
  techs: string[]
}
export interface Roadmap {
  role: string
  color: string
  // 이 로드맵으로 진입시키는 기술들(선택된 기술이 여기 속하면 로드맵 노출)
  triggers: string[]
  steps: RoadmapStep[]
}

export const ROADMAPS: Roadmap[] = [
  {
    role: '백엔드',
    color: '#60a5fa',
    triggers: [
      'Java', 'Kotlin', 'Spring', 'Spring Boot', 'Node.js', 'Django', 'FastAPI',
      'Express', 'NestJS', 'JPA', 'REST API', 'MSA', 'gRPC', 'GraphQL',
    ],
    steps: [
      { tier: '1. 언어 기초', note: '하나의 언어를 깊게. JVM 계열이 채용 비중 최다.', techs: ['Java', 'Kotlin', 'Python', 'Go'] },
      { tier: '2. 웹 프레임워크', note: '언어에 맞는 메인 프레임워크로 API 서버 작성.', techs: ['Spring Boot', 'Spring', 'Django', 'FastAPI', 'NestJS', 'Express'] },
      { tier: '3. 데이터 계층', note: 'ORM·관계형 DB·캐시. 영속성과 트랜잭션 이해.', techs: ['JPA', 'MySQL', 'PostgreSQL', 'Redis'] },
      { tier: '4. API 설계', note: 'REST 성숙도 → 스키마 기반(GraphQL)·서비스간 통신(gRPC).', techs: ['REST API', 'GraphQL', 'gRPC'] },
      { tier: '5. 메시징·비동기', note: '이벤트 기반 처리와 서비스 디커플링.', techs: ['Kafka', 'RabbitMQ', 'WebSocket'] },
      { tier: '6. 인프라·확장', note: '컨테이너화 → 오케스트레이션 → MSA 분리.', techs: ['Docker', 'Kubernetes', 'MSA', 'AWS'] },
    ],
  },
  {
    role: '프론트엔드',
    color: '#34d399',
    triggers: ['React', 'Vue', 'Angular', 'Next.js', 'Nuxt', 'Svelte', 'TypeScript', 'JavaScript', 'Redux', 'Zustand', 'jQuery', 'HTML', 'CSS', 'Tailwind'],
    steps: [
      { tier: '1. 웹 기초', note: '시맨틱 마크업·레이아웃·반응형.', techs: ['HTML', 'CSS', 'SCSS', 'Tailwind'] },
      { tier: '2. 언어', note: 'JS 핵심 → 타입 안정성(TypeScript)으로 전환이 사실상 표준.', techs: ['JavaScript', 'TypeScript'] },
      { tier: '3. 프레임워크', note: '컴포넌트 모델 하나를 주력으로. React 채용 비중 최다.', techs: ['React', 'Vue', 'Svelte', 'Angular'] },
      { tier: '4. 상태관리', note: '전역 상태·서버 상태 분리 패턴.', techs: ['Redux', 'Zustand'] },
      { tier: '5. 메타프레임워크', note: 'SSR/SSG·라우팅·풀스택 경계.', techs: ['Next.js', 'Nuxt'] },
      { tier: '6. 빌드·품질', note: '번들러·테스트로 생산성과 안정성 확보.', techs: ['Vite', 'Webpack', 'Jest'] },
    ],
  },
  {
    role: '모바일',
    color: '#fbbf24',
    triggers: ['iOS', 'Android', 'Swift', 'SwiftUI', 'Kotlin', 'Jetpack Compose', 'Flutter', 'React Native'],
    steps: [
      { tier: '1. 플랫폼 언어', note: 'iOS=Swift, Android=Kotlin.', techs: ['Swift', 'Kotlin'] },
      { tier: '2. 네이티브 UI', note: '선언형 UI 프레임워크로 화면 구성.', techs: ['SwiftUI', 'Jetpack Compose'] },
      { tier: '3. 크로스플랫폼', note: '단일 코드베이스로 양 플랫폼 동시 대응.', techs: ['Flutter', 'React Native'] },
      { tier: '4. 연동·확장', note: '네트워크·실시간·백엔드 연계.', techs: ['REST API', 'WebSocket', 'Firebase'] },
    ],
  },
  {
    role: '데이터',
    color: '#2dd4bf',
    triggers: ['Spark', 'Hadoop', 'Airflow', 'Kafka', 'Snowflake', 'BigQuery', 'dbt', 'Flink'],
    steps: [
      { tier: '1. 기초', note: 'SQL과 Python은 데이터 직군의 공용어.', techs: ['SQL', 'Python', 'Pandas'] },
      { tier: '2. 파이프라인', note: '워크플로 오케스트레이션·ETL.', techs: ['Airflow', 'dbt'] },
      { tier: '3. 분산 처리', note: '대용량 배치 처리.', techs: ['Spark', 'Hadoop'] },
      { tier: '4. 스트리밍', note: '실시간 이벤트 처리.', techs: ['Kafka', 'Flink'] },
      { tier: '5. 웨어하우스', note: '분석용 저장·쿼리 계층.', techs: ['Snowflake', 'BigQuery'] },
    ],
  },
  {
    role: 'DevOps/인프라',
    color: '#fb923c',
    triggers: ['AWS', 'GCP', 'Azure', 'Docker', 'Kubernetes', 'Terraform', 'Ansible', 'Jenkins', 'GitHub Actions', 'ArgoCD', 'Prometheus', 'Grafana', 'Linux'],
    steps: [
      { tier: '1. 운영체제', note: '리눅스·네트워크·셸 기본기.', techs: ['Linux'] },
      { tier: '2. 클라우드', note: '매니지드 인프라 위 구성·과금 이해.', techs: ['AWS', 'GCP', 'Azure'] },
      { tier: '3. 컨테이너', note: '패키징 → 오케스트레이션.', techs: ['Docker', 'Kubernetes', 'Helm', 'ArgoCD'] },
      { tier: '4. IaC', note: '인프라 코드화·재현성.', techs: ['Terraform', 'Ansible'] },
      { tier: '5. CI/CD', note: '빌드·배포 자동화 파이프라인.', techs: ['GitHub Actions', 'Jenkins', 'GitLab CI'] },
      { tier: '6. 관측성', note: '메트릭·로그·알림.', techs: ['Prometheus', 'Grafana'] },
    ],
  },
  {
    role: 'AI/ML',
    color: '#f472b6',
    triggers: ['TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'HuggingFace', 'LangChain', 'OpenAI', 'OpenCV', 'CUDA'],
    steps: [
      { tier: '1. 기초', note: 'Python·수치연산·데이터 처리.', techs: ['Python', 'NumPy', 'Pandas'] },
      { tier: '2. 머신러닝', note: '전통 ML 모델·평가.', techs: ['Scikit-learn'] },
      { tier: '3. 딥러닝', note: '프레임워크로 신경망 학습.', techs: ['PyTorch', 'TensorFlow', 'Keras'] },
      { tier: '4. LLM·생성형', note: '사전학습 모델 활용·RAG.', techs: ['HuggingFace', 'LangChain', 'OpenAI'] },
      { tier: '5. 서빙·가속', note: '추론 API·GPU 최적화.', techs: ['FastAPI', 'CUDA', 'ONNX'] },
    ],
  },
]

export function roadmapsForTech(tech: string): Roadmap[] {
  return ROADMAPS.filter((r) => r.triggers.includes(tech) || r.steps.some((s) => s.techs.includes(tech)))
}
