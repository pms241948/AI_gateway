FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies using npm ci for reproducible builds
RUN npm ci

# Copy source files
COPY . .

# Change ownership to node user (already exists in node:alpine as UID 1000)
RUN chown -R node:node /app
USER node

# Expose port
EXPOSE 3000

# Run vite using node directly (avoids PATH issues in Alpine)
CMD ["node", "node_modules/vite/bin/vite.js", "--host"]
