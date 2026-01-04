# Offline Installation Guide

This document describes how to install AI Gateway in an isolated (offline/air-gapped) environment without internet access.

## 1. Preparation (Online Environment)

### 1.1 Build and Save Docker Images

Run the following commands in an environment with internet access to build all Docker images and save them to a file:

```bash
cd ai-gateway

# Build images
docker compose build

# Pull required base images
docker pull postgres:15-alpine
docker pull redis:7-alpine
docker pull nginx:1.25-alpine

# Save all images to a tar file
docker save \
  ai_gateway-backend \
  ai_gateway-frontend \
  postgres:15-alpine \
  redis:7-alpine \
  nginx:1.25-alpine \
  -o ai_gateway_images.tar

# Compress (Optional)
gzip ai_gateway_images.tar
```

### 1.2 Package Project Files

```bash
# Compress project directory
tar -czvf ai_gateway_project.tar.gz \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='node_modules' \
  --exclude='.git' \
  .
```

### 1.3 Files to Transfer

Files to transfer to the offline environment:
- `ai_gateway_images.tar.gz` (or `.tar`) - Docker images
- `ai_gateway_project.tar.gz` - Project files

## 2. Installation (Offline Environment)

### 2.1 Copy Files

Copy the files to the offline server using a USB drive or other secure methods.

### 2.2 Load Docker Images

```bash
# Decompress (if gzipped)
gunzip ai_gateway_images.tar.gz

# Load images
docker load -i ai_gateway_images.tar

# Verify images
docker images | grep -E "(ai_gateway|postgres|redis|nginx)"
```

### 2.3 Project Setup

```bash
# Extract project files
mkdir -p /opt/ai-gateway
tar -xzvf ai_gateway_project.tar.gz -C /opt/ai-gateway
cd /opt/ai-gateway

# Configure environment variables
cp .env.example .env
```

Edit the `.env` file to change security settings:

```bash
# MUST CHANGE
SECRET_KEY=<random-string-min-32-chars>
JWT_SECRET_KEY=<another-random-string-min-32-chars>
DB_PASSWORD=<strong-database-password>
ADMIN_PASSWORD=<admin-password>
```

### 2.4 Start Services

```bash
docker compose up -d
```

### 2.5 Verify Installation

```bash
# Check service status
docker compose ps

# Health check
curl http://localhost/health

# Check logs
docker compose logs -f backend
```

## 3. Initial Configuration

### 3.1 Admin Login

1. Open browser and navigate to `http://<server-IP>`
2. Login with the admin credentials configured in `.env`
   - Default: admin@example.com / admin123

### 3.2 Provider Setup (e.g., Ollama)

If Ollama is running on the same network:

1. Admin UI → Providers → Add Provider
2. Settings:
   - Name: `local-ollama`
   - Type: `ollama`
   - Base URL: `http://<ollama-host>:11434`
3. Click "Test Connection" to verify

### 3.3 Register Model

1. Admin UI → Models → Add Model
2. Settings:
   - Alias: `llama3` (Name used by clients)
   - Display Name: `Llama 3 8B`
   - Type: `chat`
   - Endpoints: Select Provider and enter actual model name (e.g., `llama3:8b`)

## 4. TLS Configuration (Recommended)

### 4.1 Prepare Certificates

```bash
# Copy certificate files to nginx/ssl directory
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem
```

### 4.2 Configure Nginx

Uncomment the HTTPS server block in `nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl http2;
    # ... SSL settings ...
}
```

### 4.3 Restart Service

```bash
docker compose restart nginx
```

## 5. Backup and Restore

### 5.1 Database Backup

```bash
# Backup
docker compose exec postgres pg_dump -U ai_gateway ai_gateway > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres psql -U ai_gateway ai_gateway < backup_20240101.sql
```

### 5.2 Full Volume Backup

```bash
# Check volume path
docker volume inspect ai_gateway_postgres_data

# Backup (Recommended to stop service first)
docker compose stop postgres
docker run --rm -v ai_gateway_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data.tar.gz /data
docker compose start postgres
```

## 6. Troubleshooting

### 6.1 Services Not Starting

```bash
# Check all logs
docker compose logs

# Check specific service logs
docker compose logs backend
docker compose logs postgres
```

### 6.2 Database Connection Failure

```bash
# Check PostgreSQL status
docker compose exec postgres pg_isready -U ai_gateway
```

### 6.3 Out of Memory

Add resource limits to `docker-compose.yml`:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 1G
```

## 7. Installing Optional Components

### 7.1 Presidio (PII Masking)

Save and transfer Presidio images as well:

```bash
# Online
docker pull mcr.microsoft.com/presidio-analyzer:latest
docker pull mcr.microsoft.com/presidio-anonymizer:latest
docker save mcr.microsoft.com/presidio-analyzer mcr.microsoft.com/presidio-anonymizer -o presidio_images.tar

# Offline
docker load -i presidio_images.tar

# Start Service
docker compose --profile masking up -d
```

### 7.2 Keycloak (SSO)

```bash
# Online
docker pull quay.io/keycloak/keycloak:22.0
docker save quay.io/keycloak/keycloak:22.0 -o keycloak_image.tar

# Offline
docker load -i keycloak_image.tar

# Start Service
docker compose --profile sso up -d
```
