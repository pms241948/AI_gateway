#!/bin/bash
# Import Docker images in offline environment

set -e

if [ ! -f "ai_gateway_images.tar.gz" ] && [ ! -f "ai_gateway_images.tar" ]; then
  echo "Error: ai_gateway_images.tar.gz or ai_gateway_images.tar not found"
  exit 1
fi

if [ -f "ai_gateway_images.tar.gz" ]; then
  echo "Decompressing..."
  gunzip -k ai_gateway_images.tar.gz
fi

echo "Loading images..."
docker load -i ai_gateway_images.tar

echo "Done! Loaded images:"
docker images | grep -E "(ai_gateway|postgres|redis|nginx)"
