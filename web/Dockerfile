# Hack Hamster portal frontend (web/) — multi-stage by design:
#
#   development — dev-server image, identical to the previous
#                 single-stage one. docker-compose.multi.yml pins it
#                 explicitly (build.target: development) so the local
#                 compose workflow keeps its `next dev` + volume-mount
#                 loop exactly as before.
#   production  — real `next build` + `next start` image. It is the
#                 LAST stage, so it is also the default target: a bare
#                 `docker build web/` and PaaS "Dockerfile" deployments
#                 (Dokploy-style file / context / build-stage forms)
#                 get the production image unless they explicitly
#                 request `development` by name.
#
# Build:
#   docker build web/ -t hack-hamster-frontend               # → production
#   docker build web/ --target development -t hh-web-dev      # → dev server
#
# NEXT_PUBLIC_* values are inlined into the client bundle at BUILD
# time, so the widget's public base URL is a build ARG. The empty
# default makes the widget emit relative URLs — correct for every
# deployment this repo ships, where the frontend and the /api/* it
# proxies share one public origin (nginx, the Next.js rewrite proxy,
# single-domain PaaS setups):
#   docker build web/ --build-arg NEXT_PUBLIC_WIDGET_BASE=https://portal.example.com
#
# Base matches the all-in-one image's proven in-container build
# environment (Debian, glibc SWC binaries) rather than alpine/musl.

FROM node:22-bookworm-slim AS development

WORKDIR /app

# Layer-cached: install deps first so source edits don't bust this.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --prefer-offline

COPY . .

ENV NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

# Dev server — matches the rest of the stack (Django also runs its
# dev server, not gunicorn, per docker-compose.yml).
CMD ["npm", "run", "dev"]

# --- production: compile in the builder, run from a clean base -------------

FROM development AS builder

# Inlined into the client bundle by `next build` (see header note).
ARG NEXT_PUBLIC_WIDGET_BASE=""
ENV NEXT_PUBLIC_WIDGET_BASE=$NEXT_PUBLIC_WIDGET_BASE

RUN npm run build

FROM node:22-bookworm-slim AS production

WORKDIR /app

# Server-side (SSR) reads of the same variable happen at RUNTIME, so
# the image default must match what the client bundle was baked with.
ARG NEXT_PUBLIC_WIDGET_BASE=""
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_WIDGET_BASE=$NEXT_PUBLIC_WIDGET_BASE

COPY --from=builder /app ./

EXPOSE 3000

# `npm run start` = `next start -H 0.0.0.0` — binds all interfaces so
# PaaS port mappings and healthchecks reach it. Server-side /api/*
# requests are rewritten to API_INTERNAL_URL (next.config.ts), so set
# that env per deployment.
CMD ["npm", "run", "start"]
