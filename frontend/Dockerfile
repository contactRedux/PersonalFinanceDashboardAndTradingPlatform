FROM node:20-slim

WORKDIR /app

# Copy package manifests and install deps as root (faster, avoids permission issues during install)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source
COPY . .

# Build production bundle
RUN npm run build

# Transfer ownership of the entire app directory to the node user
# (covers node_modules, .next build output, and source files)
RUN chown -R node:node /app

# Drop to non-root user
USER node

EXPOSE 3000

CMD ["npm", "start"]
