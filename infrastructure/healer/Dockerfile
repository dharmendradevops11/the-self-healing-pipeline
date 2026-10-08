FROM node:22-alpine AS base
# Pinned for reproducible installs. Newer pnpm majors reject very recently published packages.
ARG PNPM_VERSION=9
RUN apk add --no-cache git openssh-client python3 make g++ \
 && npm install -g pnpm@${PNPM_VERSION}
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY dist/tasks/ ./tasks/
ENV AWS_REGION=us-east-2
ENV NODE_ENV=production
CMD ["node", "tasks/investigate/run.js"]
