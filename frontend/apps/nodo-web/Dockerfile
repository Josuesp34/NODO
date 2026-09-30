# syntax=docker/dockerfile:1.7
FROM node:22-alpine AS dependencies
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/nodo-web/package.json apps/nodo-web/package.json
COPY apps/nodo-lab/package.json apps/nodo-lab/package.json
COPY apps/nodo-mobile/package.json apps/nodo-mobile/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN npm ci --workspace=@nodo/web --include-workspace-root

FROM node:22-alpine AS builder
WORKDIR /workspace
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=dependencies /workspace/node_modules ./node_modules
COPY . .
RUN npm run build:web

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=8080

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 --ingroup nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /workspace/apps/nodo-web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/nodo-web/.next/static ./apps/nodo-web/.next/static
COPY --from=builder --chown=nextjs:nodejs /workspace/apps/nodo-web/public ./apps/nodo-web/public

USER nextjs
EXPOSE 8080
CMD ["node", "apps/nodo-web/server.js"]
