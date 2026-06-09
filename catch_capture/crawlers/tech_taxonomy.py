"""기술 블로그용 세분화 기술 키워드 택소노미 (LLM 없이 정규식 추출).

잡 크롤러가 쓰는 jobs_common.TECH_KEYWORDS 와 별개로, 블로그 본문(산문)에서
언어/프레임워크/AI·ML/LLM·생성형/알고리즘·이론/펌웨어·임베디드/시스템/보안/
데이터/인프라/그래픽·게임/블록체인/연구 등 폭넓은 주제를 카테고리별로 추출한다.

산문에서 흔한 영단어(Go, Rust, Swift, Spark…)는 오탐을 막기 위해 대소문자를
구분(CASE_SENSITIVE)하고, Graph/Tree/Attention 같은 너무 일반적인 단어는
다어절 형태(Dynamic Programming, Attention Mechanism…)로만 잡는다.

  extract_tech_tags(text) -> list[str]      # 매칭된 canonical 목록(카테고리 정렬)
  CATEGORY_OF: dict[str, str]               # canonical -> 카테고리
  CATEGORIES: list[str]                     # 카테고리 표시 순서
"""
from __future__ import annotations

import re

# 카테고리 표시 순서
CATEGORIES = [
    "언어",
    "프론트엔드",
    "백엔드",
    "모바일",
    "AI/ML",
    "LLM/생성형",
    "데이터",
    "데이터베이스",
    "인프라/클라우드",
    "관측성",
    "시스템/OS",
    "알고리즘/이론",
    "펌웨어/임베디드",
    "보안",
    "그래픽/게임",
    "블록체인",
    "연구/논문",
    "협업/도구",
]

# canonical: [별칭...]  — 별칭은 매칭만 추가하고 결과는 canonical 로 통일
# 카테고리별 묶음
_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "언어": {
        "Java": [], "Kotlin": [], "Python": [], "JavaScript": ["JS"], "TypeScript": ["TS"],
        "C++": ["Cpp"], "C#": ["C Sharp"], "Go": ["Golang"], "Rust": [], "Ruby": [],
        "PHP": [], "Swift": [], "Scala": [], "Dart": [], "Perl": [], "Julia": [],
        "Elixir": [], "Erlang": [], "Haskell": [], "Clojure": [], "Lua": [], "Zig": [],
        "Objective-C": ["Objective C"], "Assembly": ["어셈블리"], "Bash": ["Shell Script"],
        "Solidity": [], "F#": [], "OCaml": [], "Groovy": [], "MATLAB": [], "SQL": [],
        "Verilog": [], "VHDL": [],
    },
    "프론트엔드": {
        "React": [], "Vue": ["Vue.js"], "Angular": [], "Next.js": ["NextJS"], "Nuxt": [],
        "Svelte": ["SvelteKit"], "SolidJS": ["Solid.js"], "Qwik": [], "Remix": [],
        "Astro": [], "jQuery": [], "HTML": ["HTML5"], "CSS": ["CSS3"], "SCSS": [],
        "SASS": [], "Tailwind": ["TailwindCSS"], "Webpack": [], "Vite": [], "Babel": [],
        "Redux": [], "Zustand": [], "MobX": [], "Storybook": [], "Three.js": ["ThreeJS"],
        "WebGL": [], "WebAssembly": ["WASM"], "WebRTC": [], "PWA": [],
    },
    "백엔드": {
        "Node.js": ["NodeJS"], "Deno": [], "Bun": [], "Spring": [], "Spring Boot": [],
        "Django": [], "Flask": [], "FastAPI": [], "Express": ["Express.js"],
        "NestJS": ["Nest.js"], "Rails": ["Ruby on Rails"], ".NET": ["ASP.NET", "dotnet"],
        "Laravel": [], "Gin": [], "Echo": [], "Fiber": [], "Actix": [], "Phoenix": [],
        "Ktor": [], "Quarkus": [], "Micronaut": [], "Netty": [], "gRPC": [],
        "GraphQL": [], "REST API": ["RESTful"], "WebSocket": [], "Protobuf": ["Protocol Buffers"],
    },
    "모바일": {
        "iOS": [], "Android": [], "Flutter": [], "React Native": [], "SwiftUI": [],
        "Jetpack Compose": ["Compose"], "Kotlin Multiplatform": ["KMP", "KMM"],
        "UIKit": [], "Xamarin": [], "Ionic": [],
    },
    "AI/ML": {
        "Machine Learning": ["머신러닝", "ML"], "Deep Learning": ["딥러닝"],
        "TensorFlow": [], "PyTorch": [], "JAX": [], "Keras": [], "Scikit-learn": ["sklearn"],
        "XGBoost": [], "LightGBM": [], "OpenCV": [], "ONNX": [], "MLflow": [],
        "Kubeflow": [], "Ray": [], "CUDA": [], "TensorRT": [], "Triton": [],
        "Computer Vision": ["컴퓨터 비전"], "NLP": ["자연어 처리"], "Speech Recognition": ["음성인식"],
        "Reinforcement Learning": ["강화학습"], "Recommendation System": ["추천 시스템", "추천시스템"],
        "Federated Learning": [], "AutoML": [], "MLOps": [], "Feature Store": [],
        "Anomaly Detection": ["이상탐지"], "Time Series": ["시계열"], "Graph Neural Network": ["GNN"],
        "CNN": [], "RNN": ["LSTM"], "Knowledge Distillation": [],
    },
    "LLM/생성형": {
        "LLM": ["대규모 언어 모델", "거대언어모델"], "GPT": ["ChatGPT", "GPT-4"], "Claude": [],
        "Gemini": [], "Llama": ["LLaMA"], "Mistral": [], "BERT": [], "Transformer": [],
        "Attention Mechanism": ["Self-Attention"], "RAG": ["Retrieval Augmented Generation"],
        "Embedding": ["임베딩"], "Fine-tuning": ["파인튜닝"], "LoRA": ["QLoRA"], "PEFT": [],
        "Prompt Engineering": ["프롬프트 엔지니어링", "Prompting"], "LangChain": [],
        "LlamaIndex": [], "vLLM": [], "Diffusion": ["Stable Diffusion"], "GAN": [],
        "VAE": [], "Multimodal": ["멀티모달"], "AI Agent": ["LLM Agent", "Agentic"],
        "Vector Search": ["Semantic Search"], "Quantization": ["양자화"], "MoE": ["Mixture of Experts"],
        "RLHF": [], "DPO": [], "Whisper": [], "CLIP": [], "Hugging Face": ["HuggingFace"],
        "Model Context Protocol": ["MCP"],
    },
    "데이터": {
        "Kafka": [], "RabbitMQ": [], "Pulsar": [], "Spark": ["Apache Spark"],
        "Flink": ["Apache Flink"], "Hadoop": [], "Airflow": [], "dbt": [], "Beam": ["Apache Beam"],
        "Kinesis": [], "Debezium": [], "Iceberg": ["Apache Iceberg"], "Hudi": [],
        "Delta Lake": [], "Presto": [], "Trino": [], "Hive": [], "Data Pipeline": ["데이터 파이프라인"],
        "Data Lake": ["데이터 레이크", "Lakehouse"], "CDC": ["Change Data Capture"],
        "Stream Processing": ["스트림 처리"], "ETL": ["ELT"],
    },
    "데이터베이스": {
        "MySQL": [], "PostgreSQL": ["Postgres"], "MongoDB": [], "Redis": [], "Oracle": [],
        "MariaDB": [], "MSSQL": ["SQL Server"], "Elasticsearch": ["ELK"], "DynamoDB": [],
        "Cassandra": [], "ScyllaDB": [], "CockroachDB": [], "Neo4j": [], "ClickHouse": [],
        "InfluxDB": [], "TimescaleDB": [], "SQLite": [], "Snowflake": [], "BigQuery": [],
        "Redshift": [], "Databricks": [], "DuckDB": [], "Pinecone": [], "Milvus": [],
        "Weaviate": [], "Qdrant": [], "pgvector": [], "Vector Database": ["Vector DB", "벡터 DB"],
    },
    "인프라/클라우드": {
        "AWS": [], "GCP": ["Google Cloud"], "Azure": [], "Docker": [], "Kubernetes": ["K8s"],
        "Helm": [], "Istio": [], "Envoy": [], "Jenkins": [], "GitLab CI": [],
        "GitHub Actions": [], "ArgoCD": ["Argo CD"], "Terraform": [], "Pulumi": [],
        "Ansible": [], "Nginx": [], "Apache HTTP": [], "HAProxy": [], "Cloudflare": [],
        "Vercel": [], "Netlify": [], "Serverless": ["서버리스"], "AWS Lambda": ["Lambda"],
        "Vault": ["HashiCorp Vault"], "Consul": [], "Nomad": [], "Service Mesh": [],
        "CI/CD": [], "GitOps": [], "Spinnaker": [],
    },
    "관측성": {
        "Prometheus": [], "Grafana": [], "Datadog": [], "OpenTelemetry": ["OTel"],
        "Loki": [], "Jaeger": [], "Sentry": [], "Observability": ["관측성"],
        "Distributed Tracing": ["분산 추적"], "APM": [],
    },
    "시스템/OS": {
        "Linux": [], "Unix": [], "Kernel": ["커널"], "eBPF": [], "systemd": [],
        "containerd": [], "QEMU": [], "Virtualization": ["가상화"], "io_uring": [],
        "Memory Management": ["메모리 관리"], "File System": ["파일시스템"],
    },
    "알고리즘/이론": {
        "Algorithm": ["알고리즘"], "Data Structure": ["자료구조"],
        "Dynamic Programming": ["동적 계획법"], "Binary Search": ["이진 탐색"],
        "Hash Table": ["해시 테이블", "Hashing"], "Consistent Hashing": [],
        "Bloom Filter": [], "B-Tree": [], "LSM Tree": [], "Trie": [],
        "Concurrency": ["동시성"], "Distributed System": ["분산 시스템", "분산시스템"],
        "Consensus": ["합의 알고리즘"], "Raft": [], "Paxos": [], "CAP Theorem": [],
        "MapReduce": [], "CRDT": [], "Event Sourcing": [], "CQRS": [], "Saga Pattern": [],
        "Compiler": ["컴파일러"], "Garbage Collection": ["GC"],
        "Time Complexity": ["Big O", "Big-O", "시간 복잡도", "공간 복잡도"],
        "Graph Algorithm": ["그래프 알고리즘"], "Sorting Algorithm": ["정렬 알고리즘"],
    },
    "펌웨어/임베디드": {
        "Firmware": ["펌웨어"], "Embedded": ["임베디드"], "RTOS": [], "FreeRTOS": [],
        "Zephyr": [], "ARM": ["ARM Cortex"], "RISC-V": [], "FPGA": [], "Microcontroller": ["MCU"],
        "Bare-metal": ["베어메탈"], "Bootloader": ["U-Boot"], "Device Driver": ["디바이스 드라이버"],
        "I2C": [], "SPI": [], "UART": [], "CAN bus": ["CAN Bus"], "GPIO": [], "DMA": [],
        "Linux Kernel": [], "Yocto": [], "DSP": [], "IoT": ["사물인터넷"], "Edge Computing": ["엣지 컴퓨팅"],
        "Bluetooth": ["BLE"], "Zigbee": [], "LoRa": ["LoRaWAN"], "MQTT": [],
    },
    "보안": {
        "Security": ["보안"], "Cryptography": ["암호학", "암호화"], "OAuth": ["OAuth2"],
        "JWT": [], "TLS": ["SSL"], "OWASP": [], "Penetration Testing": ["모의해킹", "Pentest"],
        "Zero Trust": [], "SIEM": [], "WAF": [], "DDoS": [], "Reverse Engineering": ["리버스 엔지니어링"],
        "Fuzzing": [], "CVE": [], "XSS": [], "SQL Injection": [], "Authentication": ["인증"],
    },
    "그래픽/게임": {
        "Unity": [], "Unreal Engine": ["Unreal", "언리얼"], "OpenGL": [], "Vulkan": [],
        "DirectX": [], "Metal API": [], "Shader": ["셰이더"], "Ray Tracing": ["레이트레이싱"],
        "Game Engine": ["게임 엔진"], "Cocos": [],
    },
    "블록체인": {
        "Blockchain": ["블록체인"], "Ethereum": ["이더리움"], "Smart Contract": ["스마트 컨트랙트"],
        "Web3": [], "Bitcoin": ["비트코인"], "zkSNARK": ["Zero Knowledge", "영지식"], "DeFi": [],
        "Solana": [],
    },
    "연구/논문": {
        "arXiv": [], "Paper Review": ["논문 리뷰", "논문리뷰"], "Benchmark": ["벤치마크"],
        "State of the Art": ["SOTA"], "Ablation Study": ["Ablation"],
    },
    "협업/도구": {
        "Git": [], "Jira": [], "Confluence": [], "Notion": [], "Figma": [],
        "Monorepo": ["모노레포"], "A/B Test": ["AB 테스트", "A/B Testing"],
        "Design System": ["디자인 시스템"], "TDD": [], "DDD": ["Domain Driven Design"],
    },
}

# 산문에서 흔한 영단어 → 대소문자 구분(소문자 오탐 차단). canonical 기준.
CASE_SENSITIVE = {
    "Go", "Rust", "Swift", "Ray", "Spark", "Echo", "Gin", "Fiber", "Hive", "Beam",
    "Phoenix", "Remix", "Astro", "Vault", "Consul", "Nomad", "Pulsar", "Lua", "Zig",
    "Metal API", "ARM", "CLIP", "Whisper", "Llama", "Gemini", "Claude", "Trino",
    "Presto", "Bun", "Deno", "LoRa",
}

# canonical -> 카테고리
CATEGORY_OF: dict[str, str] = {}
# (canonical, compiled_pattern) 목록
_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = []


def _build_pattern(canonical: str, aliases: list[str]) -> "re.Pattern[str]":
    terms = [canonical, *aliases]
    alts = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    # 양옆이 영숫자/한글이 아니어야 (단어 경계). '.', '+', '#', '/' 등은 토큰 일부라 허용.
    pat = rf"(?<![A-Za-z0-9가-힣])(?:{alts})(?![A-Za-z0-9가-힣])"
    flags = 0 if canonical in CASE_SENSITIVE else re.IGNORECASE
    return re.compile(pat, flags)


for _cat, _entries in _TAXONOMY.items():
    for _canon, _aliases in _entries.items():
        CATEGORY_OF[_canon] = _cat
        _PATTERNS.append((_canon, _build_pattern(_canon, _aliases)))

# 카테고리 정렬 인덱스
_CAT_INDEX = {c: i for i, c in enumerate(CATEGORIES)}


def extract_tech_tags(text: str) -> list[str]:
    """본문에서 기술 태그(canonical) 추출. 카테고리 순 → 이름 순 정렬."""
    if not text:
        return []
    found = [canon for canon, rx in _PATTERNS if rx.search(text)]
    found.sort(key=lambda c: (_CAT_INDEX.get(CATEGORY_OF.get(c, ""), 999), c.lower()))
    return found


def categories_of(tags: list[str]) -> list[str]:
    """태그 목록 → 등장 카테고리(표시 순서)."""
    cats = {CATEGORY_OF.get(t) for t in tags if CATEGORY_OF.get(t)}
    return [c for c in CATEGORIES if c in cats]


if __name__ == "__main__":
    import sys
    total = len(_PATTERNS)
    print(f"택소노미: {len(CATEGORIES)}개 카테고리 · {total}개 키워드")
    sample = "We fine-tuned a Llama model with LoRA and served it via vLLM on Kubernetes. " \
             "Used RAG with pgvector. Firmware runs on FreeRTOS over I2C. go to the store."
    if len(sys.argv) > 1:
        sample = sys.argv[1]
    print("추출:", extract_tech_tags(sample))
