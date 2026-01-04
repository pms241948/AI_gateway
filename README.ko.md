# AI Gateway

<div align="center">

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-required-blue.svg)

**엔터프라이즈급 LLM 게이트웨이 솔루션**

[English Documentation](./README.md) | [API 문서](./docs/api.md) | [관리자 가이드](./docs/admin-guide.ko.md) | [오프라인 설치 가이드](./docs/offline-installation.ko.md)

</div>

---

## 개요

AI Gateway는 기업 환경을 위한 종합적인 LLM(Large Language Model) 게이트웨이 솔루션입니다. OpenAI 호환 통합 API 인터페이스를 제공하며, 다양한 LLM 프로바이더를 지원하고 강력한 보안, 접근 제어, 모니터링 기능을 제공합니다.

### 주요 기능

![대시보드 개요](./dashboard_screenshot_1767531724148.png)

| 카테고리 | 기능 |
|----------|------|
| **API 호환성** | OpenAI 호환 엔드포인트 (`/v1/chat/completions`, `/v1/embeddings`) |
| **다중 프로바이더** | Ollama, vLLM, OpenAI, Anthropic, Azure OpenAI, 커스텀 엔드포인트 |
| **보안** | Garak AI 보안 스캔, PII 탐지 및 마스킹, 입출력 필터링 |
| **접근 제어** | 사용자/조직/그룹 기반 권한, API 키 관리, SSO (OIDC) |
| **모니터링** | 요청/응답 로깅, 사용량 분석 대시보드, 실시간 메트릭 |
| **배포** | Docker Compose, 오프라인 설치 지원, 프로덕션 지원 |

---

## 아키텍처

```
┌────────────────┐      ┌────────────────┐      ┌────────────────┐
│     클라이언트   │─────▶│     Nginx      │─────▶│    FastAPI     │
│   (API/Admin)  │      │  (리버스 프록시) │      │   (백엔드)      │
└────────────────┘      └────────────────┘      └────────────────┘
                                                        │
               ┌────────────────────────────────────────┼────────────────┐
               │                    │                   │                │
        ┌──────▼──────┐     ┌───────▼──────┐    ┌──────▼──────┐  ┌──────▼──────┐
        │   Ollama    │     │     vLLM     │    │   OpenAI    │  │  PostgreSQL │
        │  (로컬 AI)   │     │ (자체 호스팅) │    │   (클라우드)  │  │  (데이터베이스)│
        └─────────────┘     └──────────────┘    └─────────────┘  └─────────────┘
                                                                         │
                                                                  ┌──────▼──────┐
                                                                  │    Redis    │
                                                                  │   (캐시)    │
                                                                  └─────────────┘
```

---

## 빠른 시작

### 사전 요구사항

- Docker 20.10+
- Docker Compose 2.0+
- 권장 RAM 4GB+

### 설치

```bash
# 저장소 클론
git clone https://github.com/your-org/ai-gateway.git
cd ai-gateway

# 환경 설정
cp .env.example .env
# .env 파일을 설정에 맞게 편집

# 서비스 시작
docker compose up -d

# 상태 확인
docker compose ps
```

### 접속 정보

| 서비스 | URL | 설명 |
|--------|-----|------|
| Admin UI | http://localhost:3000 | 웹 관리 패널 |
| API | http://localhost:8000/v1/ | OpenAI 호환 API |
| API 문서 | http://localhost:8000/docs | Swagger 문서 |

### 기본 계정

- **이메일**: `admin@example.com`
- **비밀번호**: `admin123`

> ⚠️ **중요**: 프로덕션 환경에서는 반드시 기본 계정 정보를 변경하세요!

---

## 환경 설정

### 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `SECRET_KEY` | 애플리케이션 비밀키 | `change-me-in-production` |
| `JWT_SECRET_KEY` | JWT 서명 키 | `change-me-in-production` |
| `DB_PASSWORD` | PostgreSQL 비밀번호 | `password` |
| `ADMIN_EMAIL` | 초기 관리자 이메일 | `admin@example.com` |
| `ADMIN_PASSWORD` | 초기 관리자 비밀번호 | `admin123` |
| `DEBUG` | 디버그 모드 | `false` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |

### 선택적 기능

```bash
# 보안 스캔 활성화 (Garak)
docker compose --profile security up -d

# Nginx와 함께 프로덕션 모드
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 사용법

### 1. 프로바이더 등록

Admin UI에서 **Providers** → **Add Provider**:

```yaml
Name: my-ollama
Type: ollama
Base URL: http://ollama:11434
Auth Type: none
```

### 2. 모델 등록

**Models** → **Add Model**:

```yaml
Alias: llama3
Display Name: Llama 3 8B
Type: chat
Endpoints:
  - Provider: my-ollama
  - Model Name: llama3:8b
```

### 3. API 호출

```bash
# Admin UI → Users → API Keys에서 API 키 발급

# Chat Completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3",
    "messages": [{"role": "user", "content": "안녕하세요!"}]
  }'

# Embeddings
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": "안녕하세요"
  }'
```

---

## 상세 기능

### 조직 관리

![가입 요청 관리](./join_requests_screenshot_1767531758439.png)

- **다중 조직 지원**: 사용자가 여러 조직에 동시에 소속 가능
- **역할 기반 접근**: 조직별 관리자, 멤버 역할
- **가입 요청 시스템**: 승인 워크플로가 포함된 요청 기반 조직 멤버십
- **조직 그룹**: 조직 내 세분화된 모델 접근 제어

### 보안 기능

- **AI 보안 스캔**: 모델 취약점 테스트를 위한 Garak 스캐너 통합
- **PII 탐지**: 민감 정보 자동 탐지 및 마스킹
- **요청 필터링**: 입출력 콘텐츠 필터링 및 모더레이션
- **감사 로깅**: 컴플라이언스를 위한 완전한 요청/응답 로깅

### 관리자 대시보드

- **사용 통계**: 실시간 사용량 차트 및 메트릭
- **모델 상태**: 엔드포인트 가용성 모니터링
- **사용자 관리**: 사용자 생성, API 키 관리
- **요청 로그**: CSV 내보내기가 가능한 검색 가능 로그 뷰어

---

## 프로덕션 배포

### 인터넷 환경

```bash
# 1. 클론 및 설정
git clone https://github.com/your-org/ai-gateway.git
cd ai-gateway
cp .env.example .env

# 2. 프로덕션 값으로 .env 편집
nano .env

# 3. 프로덕션 프로필로 빌드 및 시작
docker compose --profile security up -d --build

# 4. HTTPS를 위한 리버스 프록시 설정 (nginx/traefik)
```

### 보안 권장사항

1. `.env`의 **모든 기본 비밀번호 변경**
2. 리버스 프록시를 통한 **HTTPS 활성화**
3. 포트 접근 제한을 위한 **방화벽 설정**
4. 프로덕션에서 **속도 제한 활성화**
5. PostgreSQL 데이터 **정기 백업**

### 오프라인 설치

폐쇄망 환경 설정은 [docs/offline-installation.ko.md](./docs/offline-installation.ko.md)를 참조하세요.

---

## API 레퍼런스

### 인증

모든 API 요청은 Authorization 헤더에 API 키가 필요합니다:

```
Authorization: Bearer sk-your-api-key
```

### 엔드포인트

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| POST | `/v1/chat/completions` | Chat Completion (OpenAI 호환) |
| POST | `/v1/embeddings` | 텍스트 임베딩 |
| GET | `/v1/models` | 사용 가능한 모델 목록 |
| GET | `/health` | 헬스 체크 |

---

## 개발

### 로컬 개발

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 프론트엔드
cd frontend
npm install
npm run dev
```

### 프로젝트 구조

```
ai-gateway/
├── backend/           # FastAPI 백엔드
│   ├── app/
│   │   ├── api/       # API 라우트
│   │   ├── models/    # SQLAlchemy 모델
│   │   └── services/  # 비즈니스 로직
│   └── Dockerfile
├── frontend/          # React 관리자 UI
├── garak-service/     # 보안 스캐너
├── nginx/             # 리버스 프록시 설정
├── docs/              # 문서
└── docker-compose.yml
```

---

## 문제 해결

### 일반적인 문제

| 문제 | 해결방법 |
|------|----------|
| 데이터베이스 연결 실패 | PostgreSQL 컨테이너 상태 확인 |
| 포트 이미 사용 중 | docker-compose.yml에서 포트 매핑 변경 |
| API 401 반환 | API 키가 유효하고 만료되지 않았는지 확인 |
| 모델 로딩 안됨 | 프로바이더 엔드포인트 연결 확인 |

### 로그 확인

```bash
# 전체 로그
docker compose logs -f

# 백엔드만
docker logs ai_gateway_backend -f

# 데이터베이스
docker logs ai_gateway_postgres -f
```

---

## 기여

1. 저장소 포크
2. 기능 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 생성

---

## 라이선스

이 프로젝트는 MIT 라이선스 하에 있습니다 - 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 지원

- **이슈**: [GitHub Issues](https://github.com/your-org/ai-gateway/issues)
- **토론**: [GitHub Discussions](https://github.com/your-org/ai-gateway/discussions)
- **이메일**: support@your-org.com
