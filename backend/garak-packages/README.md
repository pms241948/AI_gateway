# Garak 오프라인 패키지 디렉토리

이 디렉토리는 폐쇄망(air-gapped) 환경에서 Garak LLM 보안 스캐너를 설치하기 위한 wheel 파일을 저장합니다.

## 디렉토리 구조

```
garak-packages/
├── garak-*.whl           # Garak 메인 패키지
├── *.whl                 # 의존성 패키지들
└── README.md             # 이 파일
```

## 초기 설정 (인터넷 환경에서)

처음 패키지를 다운로드하려면 인터넷 연결된 환경에서:

```bash
# 새 디렉토리 생성
mkdir garak-offline && cd garak-offline

# Garak 및 모든 의존성 다운로드
pip download garak -d .

# 추가 의존성 (필요한 경우)
pip download torch --index-url https://download.pytorch.org/whl/cpu -d .
```

## 업데이트 방법

### 1. 인터넷 환경에서 새 버전 다운로드

```bash
# 최신 Garak 다운로드
pip download garak -d ./new-packages

# 또는 특정 버전
pip download garak==X.Y.Z -d ./new-packages
```

### 2. 폐쇄망으로 파일 전송

USB 드라이브 등을 사용하여 다운로드한 파일들을 폐쇄망 환경으로 복사합니다.

### 3. 이 디렉토리에 파일 배치

기존 `.whl` 파일들을 새 파일로 교체합니다:

```bash
# 기존 파일 백업 (선택사항)
mv backend/garak-packages/*.whl backend/garak-packages/backup/

# 새 파일 복사
cp ./new-packages/*.whl backend/garak-packages/
```

### 4. Docker 이미지 재빌드

```bash
cd AI_gateway
docker compose build backend
docker compose up -d backend
```

## 주의사항

- **Python 버전 일치**: 다운로드할 때 사용하는 Python 버전(3.11)과 Docker 이미지의 Python 버전이 일치해야 합니다.
- **플랫폼 일치**: Linux x86_64 용 wheel 파일을 다운로드해야 합니다.

```bash
# Linux용 패키지 다운로드 (Windows에서 실행 시)
pip download garak --platform manylinux2014_x86_64 --python-version 311 --only-binary=:all: -d .
```

## 현재 버전

Garak 버전을 확인하려면:

```bash
docker exec ai_gateway_backend python -c "import garak; print(garak.__version__)"
```
