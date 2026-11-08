// Empty URLs = same origin (the dev proxy in vite.config.ts, the web entry point in production).
// The WS URL is then built from location (ws: on http, wss: on https).
export const CONFIG = {
  DJANGO_URL: import.meta.env.VITE_DJANGO_URL ?? "",
  FASTAPI_URL: import.meta.env.VITE_FASTAPI_URL ?? "",
  WS_URL: import.meta.env.VITE_WS_URL ?? "",
  // optional footer links; hidden when unset
  GITHUB_URL: import.meta.env.VITE_GITHUB_URL ?? "",
  CONTACT_EMAIL: import.meta.env.VITE_CONTACT_EMAIL ?? "",
  FETCH_TIMEOUT_MS: 10_000,
  // reconnects after a network drop only; backoff 1, 2, 4, 8, 16 s
  WS_RECONNECT_MAX_ATTEMPTS: 5,
  WS_RECONNECT_BASE_MS: 1_000,
} as const
