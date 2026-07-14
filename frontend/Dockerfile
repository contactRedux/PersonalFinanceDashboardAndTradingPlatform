FROM registry.redhat.io/ubi9/nodejs-20-minimal:latest

WORKDIR /app

# Copy package manifests
COPY package.json package-lock.json ./

# Install all deps (including devDeps needed for build)
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Non-root user (ubi9 default is uid 1001)
USER 1001

EXPOSE 3000

CMD ["npm", "start"]
