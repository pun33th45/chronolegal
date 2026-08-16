# =============================================================================
# ChronoLegal Frontend - Multi-stage Dockerfile
# =============================================================================

FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./

# --- Development ---
FROM base AS development
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --- Build ---
# Vite inlines import.meta.env.VITE_* at build time, so these must be
# declared as build ARGs and reach `npm run build`'s environment — CD
# passes them via --build-arg (see .github/workflows/cd.yml), but without
# a matching ARG here Docker silently drops them ("build-arg not consumed"),
# and the bundle falls back to the http://localhost:8000 default baked into
# the frontend code, breaking every real user's browser in production.
FROM base AS build
ARG VITE_API_BASE_URL
RUN npm ci --include=dev
COPY . .
RUN npm run build

# --- Production ---
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
