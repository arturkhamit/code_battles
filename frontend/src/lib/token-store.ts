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

  setRefresh: (refresh: string) => {
    localStorage.setItem(STORAGE_KEYS.REFRESH, refresh)
  },

  clear: () => {
    localStorage.removeItem(STORAGE_KEYS.ACCESS)
    localStorage.removeItem(STORAGE_KEYS.REFRESH)
    localStorage.removeItem(STORAGE_KEYS.USERNAME)
  },
}

export const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  try {
    const segment = token.split(".")[1]
    if (!segment) return null
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

const EXPIRY_MARGIN_S = 30

const isFresh = (token: string): boolean => {
  const exp = decodeJwtPayload(token)?.exp
  return typeof exp === "number" && exp - EXPIRY_MARGIN_S > Date.now() / 1000
}

const postRefresh = (refresh: string) =>
  safeFetch<{ access: string; refresh?: string }>(
    `${CONFIG.DJANGO_URL}/api/accounts/refresh/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    },
  )

// 401 (or 400): the server rejected this refresh token. Anything else (network, 429, 5xx) is not
// a verdict on the session.
const isRejected = (status: number) => status === 401 || status === 400

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// Refresh tokens are single-use. Another tab may have rotated ours a moment ago: give it a
// moment to save the new one. navigator.locks would serialize this, but it needs a secure context.
const rotatedElsewhere = async (sent: string): Promise<string | null> => {
  if (tokenStore.getRefresh() === sent) await sleep(500)
  const current = tokenStore.getRefresh()
  return current && current !== sent ? current : null
}

let refreshPromise: Promise<string | null> | null = null

/**
 * A new access token, or null. The session is cleared only when the server rejects the refresh
 * token twice: once as read, once more after re-reading it from localStorage. A network error,
 * 429 or 5xx keeps the session as it is.
 */
export const refreshAccessToken = (): Promise<string | null> => {
  refreshPromise ??= (async () => {
    let sent = tokenStore.getRefresh()
    if (!sent) return null

    let result = await postRefresh(sent)
    if (!result.ok && isRejected(result.error.status)) {
      const other = await rotatedElsewhere(sent)
      if (other) {
        sent = other
        result = await postRefresh(other)
      }
    }

    if (result.ok) {
      tokenStore.setAccess(result.data.access)
      // The server rotates refresh tokens: the one we just sent is blacklisted now.
      if (result.data.refresh) tokenStore.setRefresh(result.data.refresh)
      return result.data.access
    }
    if (!isRejected(result.error.status)) return null

    // Rejected again. If another tab rotated meanwhile, its fresh access token is ours too.
    if (await rotatedElsewhere(sent)) return tokenStore.getAccess()

    tokenStore.clear()
    window.dispatchEvent(new CustomEvent("auth:session-expired"))
    return null
  })().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

/** The stored access token if it is not about to expire, otherwise a refreshed one (or null). */
export const getFreshAccess = async (): Promise<string | null> => {
  const access = tokenStore.getAccess()
  if (access && isFresh(access)) return access
  return refreshAccessToken()
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
  // a failed refresh (network) still leaves the old token worth a try
  const access = (await getFreshAccess()) ?? tokenStore.getAccess()
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

  const withToken = (token: string): RequestInit => ({
    ...options,
    headers: mergeHeaders(options.headers, {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    }),
  })

  const result = await safeFetch<T>(url, withToken(access))

  if (!result.ok && result.error.status === 401) {
    const newAccess = await refreshAccessToken()
    if (!newAccess) return result
    return safeFetch<T>(url, withToken(newAccess))
  }

  return result
}
