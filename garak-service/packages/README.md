# Garak 오프라인 패키지 디렉토리

이 디렉토리에 `.whl` 파일을 배치하면 오프라인 환경에서 Garak이 설치됩니다.

## 업데이트 방법

```bash
# 인터넷 환경에서
pip download garak fastapi uvicorn -d ./packages

# 폐쇄망으로 복사 후 이 디렉토리에 배치
docker compose build garak
docker compose up -d garak
```
