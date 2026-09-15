FROM node:22-alpine
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
COPY pnpm-lock.yaml* ./
RUN pnpm install
COPY apps/web apps/web
COPY packages/contracts packages/contracts
WORKDIR /repo/apps/web
ARG API_URL=http://api:8000
ENV API_URL=$API_URL
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
