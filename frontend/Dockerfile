# web: builds the SPA and serves it with Caddy, which also routes /api, /ws, /admin to the
# backends (frontend/Caddyfile). Build context: frontend/
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
# VITE_* are empty by default: the browser talks to its own origin
RUN npm run build

FROM caddy:2.11.7-alpine
LABEL org.opencontainers.image.title="code-battles-web"
# The caddy binary carries file capabilities (bind to port 80). Port 8080 needs none, and with
# cap_drop ALL a binary that asks for them does not start.
# hadolint ignore=DL3018
RUN apk add --no-cache libcap-utils && setcap -r /usr/bin/caddy && apk del libcap-utils
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
# Caddy keeps state under XDG_*: tmpfs in compose (read-only rootfs)
ENV XDG_DATA_HOME=/tmp/caddy-data \
    XDG_CONFIG_HOME=/tmp/caddy-config
USER 10003:10003
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=4s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
