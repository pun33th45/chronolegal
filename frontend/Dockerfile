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
FROM base AS build
RUN npm ci --include=dev
COPY . .
RUN npm run build

# --- Production ---
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
