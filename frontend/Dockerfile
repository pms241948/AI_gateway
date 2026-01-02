FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Production image - just keeps the build artifacts
FROM alpine:latest
COPY --from=builder /app/dist /app/dist
CMD ["echo", "Build complete"]
