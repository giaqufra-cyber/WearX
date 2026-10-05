# syntax=docker/dockerfile:1.7
# Pannello dello staff (Next.js "standalone"). Si costruisce dalla radice del repository:
#   docker build -f apps/admin/Dockerfile --build-arg NEXT_PUBLIC_API_URL=... .
# I valori NEXT_PUBLIC_* sono pubblici e finiscono nel codice del browser: mai segreti qui.
#checkov:skip=CKV_DOCKER_2:Su Cloud Run la salute la controllano le sonde del servizio.

FROM node:22-bookworm-slim AS build
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
COPY apps/admin/package.json apps/admin/
COPY apps/mobile/package.json apps/mobile/
COPY packages/api-types/package.json packages/api-types/
COPY packages/design-tokens/package.json packages/design-tokens/
RUN pnpm install --frozen-lockfile --filter "@wearx/admin..."
COPY packages/api-types packages/api-types
COPY packages/design-tokens packages/design-tokens
COPY apps/admin apps/admin
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY}
RUN pnpm --filter @wearx/admin build

FROM node:22-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /repo/apps/admin/.next/standalone ./
COPY --from=build --chown=node:node /repo/apps/admin/.next/static ./apps/admin/.next/static
USER node
EXPOSE 8080
CMD ["node", "apps/admin/server.js"]
