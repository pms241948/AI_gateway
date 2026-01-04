# 오프라인 설치 가이드

이 문서는 인터넷 연결이 없는 폐쇄망 환경에 AI Gateway를 설치하는 방법을 설명합니다.

## 1. 준비 (온라인 환경)

### 1.1 Docker 이미지 빌드 및 저장

온라인 환경에서 다음 명령을 실행하여 모든 Docker 이미지를 빌드하고 파일로 저장합니다:

```bash
cd ai-gateway

# 이미지 빌드
docker compose build

# 필요한 기본 이미지 Pull
docker pull postgres:15-alpine
docker pull redis:7-alpine
docker pull nginx:1.25-alpine

# 모든 이미지를 tar 파일로 저장
docker save \
  ai_gateway-backend \
  ai_gateway-frontend \
  postgres:15-alpine \
  redis:7-alpine \
  nginx:1.25-alpine \
  -o ai_gateway_images.tar

# 압축 (선택)
gzip ai_gateway_images.tar
```

### 1.2 프로젝트 파일 패키징

```bash
# 프로젝트 디렉토리 압축
tar -czvf ai_gateway_project.tar.gz \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='node_modules' \
  --exclude='.git' \
  .
```

### 1.3 전송할 파일 목록

오프라인 환경으로 전송할 파일:
- `ai_gateway_images.tar.gz` (또는 `.tar`) - Docker 이미지
- `ai_gateway_project.tar.gz` - 프로젝트 파일

## 2. 설치 (오프라인 환경)

### 2.1 파일 복사

USB 또는 기타 방법으로 파일을 오프라인 서버로 복사합니다.

### 2.2 Docker 이미지 로드

```bash
# 압축 해제 (gzip 사용 시)
gunzip ai_gateway_images.tar.gz

# 이미지 로드
docker load -i ai_gateway_images.tar

# 이미지 확인
docker images | grep -E "(ai_gateway|postgres|redis|nginx)"
```

### 2.3 프로젝트 설정

```bash
# 프로젝트 압축 해제
mkdir -p /opt/ai-gateway
tar -xzvf ai_gateway_project.tar.gz -C /opt/ai-gateway
cd /opt/ai-gateway

# 환경 변수 설정
cp .env.example .env
```

`.env` 파일을 편집하여 보안 설정을 변경합니다:

```bash
# 반드시 변경해야 하는 값
SECRET_KEY=<랜덤-문자열-32자-이상>
JWT_SECRET_KEY=<다른-랜덤-문자열-32자-이상>
DB_PASSWORD=<강력한-비밀번호>
ADMIN_PASSWORD=<관리자-비밀번호>
```

### 2.4 서비스 시작

```bash
docker compose up -d
```

### 2.5 설치 확인

```bash
# 서비스 상태 확인
docker compose ps

# 헬스체크
curl http://localhost/health

# 로그 확인
docker compose logs -f backend
```

## 3. 초기 설정

### 3.1 관리자 로그인

1. 브라우저에서 `http://<서버-IP>` 접속
2. `.env`에 설정한 관리자 계정으로 로그인
   - 기본: admin@example.com / admin123

### 3.2 Provider 설정 (예: Ollama)

Ollama가 동일 네트워크에 있다면:

1. Admin UI → Providers → Add Provider
2. 설정:
   - Name: `local-ollama`
   - Type: `ollama`
   - Base URL: `http://<ollama-host>:11434`
3. Test Connection 클릭하여 연결 확인

### 3.3 모델 등록

1. Admin UI → Models → Add Model
2. 설정:
   - Alias: `llama3` (클라이언트가 사용할 이름)
   - Display Name: `Llama 3 8B`
   - Type: `chat`
   - Endpoints: Provider 선택 후 실제 모델명 입력 (예: `llama3:8b`)

## 4. TLS 설정 (권장)

### 4.1 인증서 준비

```bash
# 인증서 파일을 nginx/ssl 디렉토리에 복사
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

### 4.2 Nginx 설정 수정

`nginx/nginx.conf`에서 HTTPS 서버 블록 주석 해제:

```nginx
server {
    listen 443 ssl http2;
    # ... SSL 설정 ...
}
```

### 4.3 서비스 재시작

```bash
docker compose restart nginx
```

## 5. 백업 및 복구

### 5.1 데이터베이스 백업

```bash
# 백업
docker compose exec postgres pg_dump -U ai_gateway ai_gateway > backup_$(date +%Y%m%d).sql

# 복구
docker compose exec -T postgres psql -U ai_gateway ai_gateway < backup_20240101.sql
```

### 5.2 전체 볼륨 백업

```bash
# 볼륨 경로 확인
docker volume inspect ai_gateway_postgres_data

# 백업 (서비스 중지 권장)
docker compose stop postgres
docker run --rm -v ai_gateway_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz /data
docker compose start postgres
```

## 6. 문제 해결

### 6.1 서비스가 시작되지 않음

```bash
# 전체 로그 확인
docker compose logs

# 특정 서비스 로그
docker compose logs backend
docker compose logs postgres
```

### 6.2 데이터베이스 연결 실패

```bash
# PostgreSQL 상태 확인
docker compose exec postgres pg_isready -U ai_gateway
```

### 6.3 메모리 부족

`docker-compose.yml`에 리소스 제한 추가:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
```

## 7. 선택적 컴포넌트 설치

### 7.1 Presidio (PII 마스킹)

Presidio 이미지도 함께 저장하여 전송:

```bash
# 온라인 환경에서
docker pull mcr.microsoft.com/presidio-analyzer:latest
docker pull mcr.microsoft.com/presidio-anonymizer:latest
docker save mcr.microsoft.com/presidio-analyzer mcr.microsoft.com/presidio-anonymizer -o presidio_images.tar

# 오프라인 환경에서
docker load -i presidio_images.tar

# 서비스 시작
docker compose --profile masking up -d
```

### 7.2 Keycloak (SSO)

```bash
# 온라인 환경에서
docker pull quay.io/keycloak/keycloak:22.0
docker save quay.io/keycloak/keycloak:22.0 -o keycloak_image.tar

# 오프라인 환경에서
docker load -i keycloak_image.tar

# 서비스 시작
docker compose --profile sso up -d
```
