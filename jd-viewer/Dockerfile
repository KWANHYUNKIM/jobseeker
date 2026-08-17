# ── build stage ──────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── serve stage ──────────────────────────────────────────────
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
# localhost 가 아니라 127.0.0.1 을 쓴다. 컨테이너 안에서 localhost 는 ::1 로
# 먼저 풀리는데 nginx 는 `listen 80` 으로 IPv4 만 듣기 때문에 연결이 거부되고,
# 컨테이너가 실제로는 멀쩡한데 영구히 unhealthy 로 남는다.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null 2>&1 || exit 1
