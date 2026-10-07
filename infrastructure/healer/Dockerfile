FROM node:20-alpine AS base
RUN apk add --no-cache git openssh-client python3 make g++
WORKDIR /app
COPY package.json ./
RUN npm install --production
COPY dist/tasks/ ./tasks/
ENV AWS_REGION=us-east-2
ENV NODE_ENV=production
CMD ["node", "tasks/investigate/run.js"]
