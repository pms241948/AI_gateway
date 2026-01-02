# AI Gateway

오프라인 폐쇄망 환경에서 운영 가능한 LLM Gateway 솔루션입니다.

## 주요 기능

- **OpenAI 호환 API**: `/v1/chat/completions`, `/v1/embeddings` 엔드포인트
- **다중 Provider 지원**: Ollama, vLLM, OpenAI, Anthropic 등
- **모델 라우팅**: Alias 기반 라우팅, 부하 분산, 폴백
- **권한 관리**: 사용자/조직/그룹 기반 접근 제어
- **로깅 및 감사**: 모든 요청/응답 로깅, CSV 내보내기
- **통계 대시보드**: 사용량, 지연시간, 오류율 모니터링
- **헬스체크**: 모델 엔드포인트 상태 확인
- **오프라인 설치**: Docker Compose 기반 완전 오프라인 배포

## 빠른 시작

### 사전 요구사항

- Docker 20+
- Docker Compose 2+

### 설치

```bash
# 저장소 클론
git clone https://github.com/your-org/ai-gateway.git
cd ai-gateway

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 비밀키 변경

# 서비스 시작
docker compose up -d

# 상태 확인
docker compose ps
```

### 접속

- **Admin UI**: http://localhost
- **API**: http://localhost/v1/
- **API 문서**: http://localhost/docs (개발 모드)

### 기본 관리자 계정

- Email: admin@example.com (또는 .env에서 설정)
- Password: admin123 (또는 .env에서 설정)

## 사용법

### 1. Provider 등록

Admin UI에서 Provider 메뉴 → Add Provider:

```
Name: my-ollama
Type: ollama
Base URL: http://ollama:11434
Auth Type: none
```

### 2. 모델 등록

Models 메뉴 → Add Model:

```
Alias: llama3
Display Name: Llama 3 8B
Type: chat
Endpoints:
  - Provider: my-ollama
  - Provider Model Name: llama3:8b
```

### 3. API 호출

```bash
# API 키 발급 (Admin UI → Users → API Keys)

# Chat Completion
curl -X POST http://localhost/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'

# Embeddings
curl -X POST http://localhost/v1/embeddings \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": "Hello world"
  }'
```

## 오프라인 설치

오프라인 환경에 설치하려면 [docs/offline-installation.md](docs/offline-installation.md)를 참조하세요.

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SECRET_KEY` | 애플리케이션 비밀키 | change-me |
| `JWT_SECRET_KEY` | JWT 서명 키 | change-me |
| `DB_PASSWORD` | PostgreSQL 비밀번호 | password |
| `ADMIN_EMAIL` | 초기 관리자 이메일 | admin@example.com |
| `ADMIN_PASSWORD` | 초기 관리자 비밀번호 | admin123 |
| `DEBUG` | 디버그 모드 | false |
| `LOG_LEVEL` | 로그 레벨 | INFO |

## 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│    Nginx    │────▶│   FastAPI   │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                    ┌─────────┬───────────────┼───────────────┐
                    │         │               │               │
               ┌────▼───┐ ┌───▼────┐    ┌────▼───┐    ┌──────▼─────┐
               │ Ollama │ │  vLLM  │    │ OpenAI │    │ PostgreSQL │
               └────────┘ └────────┘    └────────┘    └────────────┘
```

## 라이선스

MIT License
