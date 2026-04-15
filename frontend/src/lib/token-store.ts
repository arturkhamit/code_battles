import { CONFIG } from "../config"
import { safeFetch } from "./api"

const STORAGE_KEYS = {
  ACCESS: "cb_access_token",
  REFRESH: "cb_refresh_token",
  USERNAME: "cb_username",
} as const

export const tokenStore = {
  getAccess: () => localStorage.getItem(STORAGE_KEYS.ACCESS),
  getRefresh: () => localStorage.getItem(STORAGE_KEYS.REFRESH),
  getUsername: () => localStorage.getItem(STORAGE_KEYS.USERNAME),

  set: (access: string, refresh: string, username: string) => {
    localStorage.setItem(STORAGE_KEYS.ACCESS, access)
    localStorage.setItem(STORAGE_KEYS.REFRESH, refresh)
    localStorage.setItem(STORAGE_KEYS.USERNAME, username)
  },

  setAccess: (access: string) => {
    localStorage.setItem(STORAGE_KEYS.ACCESS, access)
  },

  clear: () => {
    localStorage.removeItem(STORAGE_KEYS.ACCESS)
    localStorage.removeItem(STORAGE_KEYS.REFRESH)
    localStorage.removeItem(STORAGE_KEYS.USERNAME)
  },
}

let refreshPromise: Promise<string | null> | null = null

const refreshAccessToken = async (): Promise<string | null> => {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    const refresh = tokenStore.getRefresh()
    if (!refresh) return null

    const result = await safeFetch<{ access: string }>(
      `${CONFIG.DJANGO_URL}/api/internal/accounts/refresh/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      },
    )

    if (!result.ok) {
      tokenStore.clear()
      window.dispatchEvent(new CustomEvent("auth:session-expired"))
      return null
    }

    tokenStore.setAccess(result.data.access)
    return result.data.access
  })()

  try {
    return await refreshPromise
  } finally {
    refreshPromise = null
  }
}

const mergeHeaders = (
  existing: HeadersInit | undefined,
  extra: Record<string, string>,
): Headers => {
  const headers = new Headers(existing)
  for (const [key, value] of Object.entries(extra)) {
    headers.set(key, value)
  }
  return headers
}

export const authFetch = async <T = unknown>(
  url: string,
  options: RequestInit = {},
): ReturnType<typeof safeFetch<T>> => {
  const access = tokenStore.getAccess()
  if (!access) {
    return {
      ok: false,
      error: {
        message: "Not authenticated",
        status: 401,
        isHtml: false,
      },
    }
  }

  const authedOptions: RequestInit = {
    ...options,
    headers: mergeHeaders(options.headers, {
      Authorization: `Bearer ${access}`,
      "Content-Type": "application/json",
    }),
  }

  const result = await safeFetch<T>(url, authedOptions)

  if (!result.ok && result.error.status === 401) {
    const newAccess = await refreshAccessToken()
    if (!newAccess) return result

    const retryOptions: RequestInit = {
      ...options,
      headers: mergeHeaders(options.headers, {
        Authorization: `Bearer ${newAccess}`,
        "Content-Type": "application/json",
      }),
    }

    return safeFetch<T>(url, retryOptions)
  }

  return result
}
