# NEW: Multi-stage production Dockerfile for the Next.js 16 frontend.
# Requires output: "standalone" in next.config.ts (already added).
# Docs: frontend/node_modules/next/dist/docs/01-app/03-api-reference/05-config/01-next-config-js/output.md

# ---- deps: install node_modules ----
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
# NEW: Use ci for reproducible installs from lockfile
RUN npm ci

# ---- builder: compile Next.js app ----
FROM node:20-alpine AS builder

WORKDIR /app

# NEW: NEXT_PUBLIC_* vars are inlined at build time — must be passed as build arg
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_APP_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

# ---- runner: minimal production image ----
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# NEW: Non-root user — mirrors Next.js official Docker example
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# NEW: public/ must be copied separately (not included in standalone output)
COPY --from=builder /app/public ./public

# NEW: standalone/ contains server.js + traced node_modules — self-contained Node server
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# NEW: static assets are not auto-served by standalone server.js; copy alongside it
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# NEW: Healthcheck hits the root page; adjust if you add a dedicated /healthz route
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:3000/ >/dev/null || exit 1

# NEW: PORT and HOSTNAME can be overridden via docker-compose environment
CMD ["node", "server.js"]
