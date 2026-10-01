// catch_capture/dashboard/classifier.py 의 DEV_ROLE_RULES 를 TS 로 포팅
// (제목 + tech_stack + 일부 qualifications 텍스트 기반 멀티라벨 분류)

const RULES: Array<{ role: string; patterns: RegExp[] }> = [
  {
    role: '백엔드',
    patterns: [
      /백[\s-]?엔드|backend|back[\s-]?end|서버\s*개발|server\s*dev/i,
      /\b(API|REST|gRPC|MSA)\b/i,
      /\b(Spring|Spring\s*Boot|Django|Flask|FastAPI|Express|NestJS|Rails|Laravel|\.NET)\b/i,
      /\b(Node\.?js|Java|Kotlin|Go|Golang|Scala|Ruby|PHP)\b.*\b(개발|engineer|developer)\b/i,
      /\b(Python|Rust|C#|Scala|Ruby|PHP|Elixir)\s+(developer|engineer|programmer)\b/i,
    ],
  },
  {
    role: '프론트엔드',
    patterns: [
      /프[\s-]?론[\s-]?트[\s-]?엔드|frontend|front[\s-]?end|클라이언트\s*웹/i,
      /\b(React|Vue|Angular|Next\.?js|Nuxt|Svelte)\b/i,
      /\b(웹\s*퍼블리|publisher|UI\s*개발)\b/i,
      /\bweb\s+(developer|engineer)\b/i,
    ],
  },
  {
    role: '모바일',
    patterns: [
      /\b(iOS|Android|안드로이드|모바일\s*개발|모바일\s*앱|앱\s*개발)\b/i,
      /\b(Swift|Kotlin|Flutter|React\s*Native)\b/i,
    ],
  },
  {
    role: 'AI/ML',
    patterns: [
      /\b(AI|ML|머신러닝|딥러닝|인공지능|MLOps|데이터\s*사이언티스트?|data\s*scien(?:tist|ce)?)\b/i,
      /\b(TensorFlow|PyTorch|Keras|Scikit[-\s]?learn|HuggingFace|LangChain|OpenAI|LLM|NLP|CV|컴퓨터\s*비전)\b/i,
      /\b(데이터\s*엔지니어|data\s*engineer)\b/i,
      /\b(research\s*engineer|research\s*scientist|applied\s*scientist|ml\s*engineer|machine\s*learning)\b/i,
    ],
  },
  {
    role: '펌웨어/임베디드',
    patterns: [
      /펌웨어|firmware|임베디드|embedded|반도체\s*설계|SoC|RTOS|MCU|FPGA|디바이스\s*드라이버/i,
      /\b(C\/?C\+\+|C\+\+|어셈블리|assembly)\b.*\b(임베디드|펌웨어|hw|hardware)\b/i,
    ],
  },
  {
    role: 'DevOps/인프라',
    patterns: [
      /DevOps|SRE|MLOps|infrastructure|인프라|클라우드\s*엔지니어|cloud\s*engineer|플랫폼\s*엔지니어|platform\s*engineer|site\s*reliability/i,
      /\b(Kubernetes|K8s|Docker|Terraform|Ansible|Jenkins|GitHub\s*Actions|AWS|GCP|Azure)\b.*\b(엔지니어|engineer|운영|ops)\b/i,
      /시스템\s*운영|시스템\s*관리/i,
    ],
  },
  {
    role: '데이터',
    patterns: [
      /데이터\s*엔지니어|data\s*engineer|데이터\s*분석|data\s*analy|빅데이터|big\s*data|BI\s*개발/i,
      /\b(Hadoop|Spark|Airflow|Kafka|ETL|Snowflake|BigQuery)\b/i,
      /data\s*(scientist|governance|platform|warehouse|analyst)/i,
    ],
  },
  {
    role: '보안',
    patterns: [
      /정보\s*보안|보안\s*엔지니어|security\s*engineer|침해\s*대응|모의\s*해킹|penetration|보안\s*개발|\b(appsec|infosec|cyber\s*security|cybersecurity|application\s*security|product\s*security|cloud\s*security|security\s*researcher)\b/i,
    ],
  },
  {
    role: '게임',
    patterns: [/게임\s*개발|game\s*dev|game\s*client|game\s*server|언리얼|unreal|유니티|unity/i],
  },
  {
    role: 'QA',
    patterns: [/\bQA\b|품질\s*보증|품질\s*엔지니어|test\s*engineer|테스트\s*자동화|automation\s*test|automation\s*engineer|\bSDET\b/i],
  },
  {
    role: '풀스택',
    patterns: [/풀스택|full[\s-]?stack/i],
  },
]

export function classifyRoles(title: string, techStack: string[] = [], extraText = ''): string[] {
  const blob = [title || '', techStack.join(' '), extraText.slice(0, 500)].join(' | ')
  const roles: string[] = []
  for (const { role, patterns } of RULES) {
    if (patterns.some((p) => p.test(blob))) roles.push(role)
  }
  if (roles.includes('풀스택')) {
    if (!roles.includes('백엔드')) roles.push('백엔드')
    if (!roles.includes('프론트엔드')) roles.push('프론트엔드')
  }
  return roles.length > 0 ? roles : ['기타']
}

// 직군 색 — 흰 바탕 하나뿐이라 팔레트도 하나다(테마 전환 없음)
export const ROLE_COLORS: Record<string, string> = {
  백엔드: '#1d4ed8',
  프론트엔드: '#7e22ce',
  풀스택: '#047857',
  모바일: '#b45309',
  'AI/ML': '#be185d',
  데이터: '#0e7490',
  'DevOps/인프라': '#c2410c',
  '펌웨어/임베디드': '#6d28d9',
  보안: '#b91c1c',
  게임: '#4d7c0f',
  QA: '#475569',
  기타: '#374151',
}

// 직군 색 — 흰 바탕 하나뿐이라 짙은 계열만 쓴다(테마 전환 없음)
export function roleColor(role: string): string {
  return ROLE_COLORS[role] ?? '#374151'
}
