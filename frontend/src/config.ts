export const CONFIG = {
  DJANGO_URL: import.meta.env.VITE_DJANGO_URL ?? "",
  FASTAPI_URL: import.meta.env.VITE_FASTAPI_URL ?? "",
  WS_URL: import.meta.env.VITE_WS_URL ?? "",
  FETCH_TIMEOUT_MS: 10_000,
  WS_RECONNECT_MAX_ATTEMPTS: 3,
  WS_RECONNECT_BASE_MS: 1_000,
} as const
