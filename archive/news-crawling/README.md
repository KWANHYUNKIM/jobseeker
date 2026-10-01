# 해외 경제 뉴스 크롤링 및 블로그 포스팅 시스템

BBC, Reuters, Bloomberg 등 해외 경제 뉴스를 자동으로 크롤링하고, 한글로 번역한 후 블로그에 포스팅하는 시스템입니다.

## 주요 기능

- **뉴스 크롤링**: BBC, Reuters, Bloomberg에서 경제 관련 뉴스 자동 수집
- **자동 번역**: Google Translate 또는 OpenAI를 사용한 한글 번역
- **블로그 포스팅**: WordPress, Medium, 네이버 블로그 등 다양한 플랫폼 지원
- **스케줄링**: 정기적인 뉴스 수집 및 포스팅
- **마크다운 저장**: 번역된 기사를 마크다운 파일로 저장

## 설치 및 설정

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`env_example.txt` 파일을 참고하여 `.env` 파일을 생성하고 필요한 API 키들을 설정하세요:

```bash
cp env_example.txt .env
# .env 파일을 편집하여 실제 API 키들을 입력
```

### 3. 설정 파일 수정

`config.py` 파일에서 뉴스 소스, 키워드, 스케줄링 설정을 필요에 따라 수정하세요.

## 사용법

### 테스트 실행

```bash
python main.py test
```

### 한 번 실행

```bash
python main.py run
```

### 스케줄링 모드 (자동 실행)

```bash
python main.py schedule
```

## 지원하는 블로그 플랫폼

### WordPress
- WordPress 사이트 URL
- 사용자명과 앱 비밀번호 필요
- XML-RPC API 사용

### Medium
- Medium 액세스 토큰 필요
- Medium API 사용

### 네이버 블로그
- 네이버 개발자 센터에서 애플리케이션 등록 필요
- Client ID, Client Secret, Access Token 필요

## 파일 구조

```
news_crawling/
├── main.py              # 메인 실행 파일
├── config.py            # 설정 파일
├── news_crawler.py      # 뉴스 크롤링 모듈
├── translator.py        # 번역 모듈
├── blog_poster.py       # 블로그 포스팅 모듈
├── requirements.txt     # Python 패키지 목록
├── env_example.txt      # 환경 변수 예시
├── README.md           # 이 파일
├── logs/               # 로그 파일 저장 디렉토리
├── results/            # 결과 JSON 파일 저장 디렉토리
└── posts/              # 마크다운 파일 저장 디렉토리
```

## 설정 옵션

### 뉴스 소스 추가

`config.py`의 `NEWS_SOURCES` 딕셔너리에 새로운 뉴스 소스를 추가할 수 있습니다:

```python
NEWS_SOURCES = {
    'your_source': {
        'url': 'https://your-news-site.com/business',
        'title_selector': 'h3.article-title',
        'link_selector': 'a.article-link',
        'base_url': 'https://your-news-site.com'
    }
}
```

### 키워드 필터링

`config.py`의 `SCHEDULE_CONFIG['keywords']`에서 경제 뉴스 필터링 키워드를 수정할 수 있습니다:

```python
'keywords': ['economy', 'business', 'finance', 'market', 'trade', 'investment', 'stock', 'currency']
```

### 스케줄링 설정

크롤링 간격을 조정하려면 `SCHEDULE_CONFIG['crawl_interval_hours']`를 수정하세요.

## 주의사항

1. **API 사용량**: 번역 API와 블로그 API의 사용량 제한을 확인하세요.
2. **뉴스 소스 정책**: 각 뉴스 사이트의 이용약관을 준수하세요.
3. **저작권**: 원문 출처를 명시하고 저작권을 존중하세요.
4. **번역 품질**: 자동 번역의 품질을 확인하고 필요시 수정하세요.

## 문제 해결

### 크롤링 오류
- 네트워크 연결 확인
- 뉴스 사이트의 구조 변경 여부 확인
- User-Agent 설정 확인

### 번역 오류
- API 키 유효성 확인
- API 사용량 한도 확인
- 인터넷 연결 확인

### 블로그 포스팅 오류
- 블로그 플랫폼 설정 확인
- API 키 및 인증 정보 확인
- 블로그 플랫폼의 API 제한 확인

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 이슈를 통해 제출해 주세요. 