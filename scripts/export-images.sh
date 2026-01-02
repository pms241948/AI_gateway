#!/bin/bash
# Export Docker images for offline deployment

set -e

echo "Building images..."
docker compose build

echo "Pulling base images..."
docker pull postgres:15-alpine
docker pull redis:7-alpine
docker pull nginx:1.25-alpine

echo "Saving images to tar file..."
docker save \
  ai_gateway-backend \
  ai_gateway-frontend \
  postgres:15-alpine \
  redis:7-alpine \
  nginx:1.25-alpine \
  -o ai_gateway_images.tar

echo "Compressing..."
gzip -f ai_gateway_images.tar

echo "Done! File created: ai_gateway_images.tar.gz"
ls -lh ai_gateway_images.tar.gz
