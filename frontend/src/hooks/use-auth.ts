import { useCallback, useEffect, useReducer } from "react"
import { CONFIG } from "../config"
import { safeFetch } from "../lib/api"
import { tokenStore } from "../lib/token-store"
import type { ApiErrorState } from "../types/battle"
import type {
  AuthState,
  AuthTokens,
  AuthUser,
  LoginRequest,
  RegisterRequest,
} from "../types/auth"

type Action =
  | { type: "SET_LOADING" }
  | { type: "SET_ANONYMOUS" }
  | { type: "SET_AUTHENTICATED"; user: AuthUser; tokens: AuthTokens }
  | { type: "SET_ERROR"; error: ApiErrorState | null }

type State = {
  auth: AuthState
  error: ApiErrorState | null
}

const initialState: State = {
  auth: { status: "loading" },
  error: null,
}

const reducer = (state: State, action: Action): State => {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, auth: { status: "loading" } }
    case "SET_ANONYMOUS":
      return { ...state, auth: { status: "anonymous" }, error: null }
    case "SET_AUTHENTICATED":
      return {
        ...state,
        auth: {
          status: "authenticated",
          user: action.user,
          tokens: action.tokens,
        },
        error: null,
      }
    case "SET_ERROR":
      return { ...state, error: action.error }
    default:
      return state
  }
}

const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  try {
    const segment = token.split(".")[1]
    if (!segment) return null
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
    const json = atob(padded)
    return JSON.parse(json)
  } catch {
    return null
  }
}

const extractUserFromTokens = (
  tokens: AuthTokens,
  fallbackUsername?: string,
): AuthUser | null => {
  const payload = decodeJwtPayload(tokens.access)

  if (!payload || payload.user_id === undefined || payload.user_id === null) {
    return null
  }

  const userId = Number(payload.user_id)

  if (isNaN(userId)) {
    return null
  }

  return {
    id: userId,
    username:
      (typeof payload.username === "string"
        ? payload.username
        : fallbackUsername) ?? "",
    email: typeof payload.email === "string" ? payload.email : "",
  }
}

export const useAuth = () => {
  const [state, dispatch] = useReducer(reducer, initialState)

  const refreshTokens = useCallback(async (refreshToken: string) => {
    const result = await safeFetch<{ access: string }>(
      `${CONFIG.DJANGO_URL}/api/internal/accounts/refresh/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: refreshToken }),
      },
    )

    if (!result.ok) {
      tokenStore.clear()
      dispatch({ type: "SET_ANONYMOUS" })
      return
    }

    const newTokens: AuthTokens = {
      access: result.data.access,
      refresh: refreshToken,
    }

    const storedUsername = tokenStore.getUsername() ?? ""
    const user = extractUserFromTokens(newTokens, storedUsername)

    if (!user) {
      tokenStore.clear()
      dispatch({ type: "SET_ANONYMOUS" })
      return
    }

    tokenStore.set(newTokens.access, newTokens.refresh, user.username)
    dispatch({ type: "SET_AUTHENTICATED", user, tokens: newTokens })
  }, [])

  useEffect(() => {
    const storedRefresh = tokenStore.getRefresh()
    if (storedRefresh) {
      refreshTokens(storedRefresh)
    } else {
      dispatch({ type: "SET_ANONYMOUS" })
    }
  }, [refreshTokens])

  useEffect(() => {
    const handleSessionExpired = () => {
      dispatch({ type: "SET_ANONYMOUS" })
    }
    window.addEventListener("auth:session-expired", handleSessionExpired)
    return () =>
      window.removeEventListener("auth:session-expired", handleSessionExpired)
  }, [])

  const login = useCallback(async (data: LoginRequest) => {
    dispatch({ type: "SET_LOADING" })
    dispatch({ type: "SET_ERROR", error: null })

    const result = await safeFetch<{ access: string; refresh: string }>(
      `${CONFIG.DJANGO_URL}/api/internal/accounts/login/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    )

    if (!result.ok) {
      dispatch({ type: "SET_ANONYMOUS" })
      dispatch({ type: "SET_ERROR", error: result.error })
      return
    }

    const tokens: AuthTokens = {
      access: result.data.access,
      refresh: result.data.refresh,
    }

    const user = extractUserFromTokens(tokens, data.username)
    if (!user) {
      dispatch({ type: "SET_ANONYMOUS" })
      dispatch({
        type: "SET_ERROR",
        error: {
          message: "Login succeeded but failed to read user info from token",
          status: 0,
          isHtml: false,
        },
      })
      return
    }

    tokenStore.set(tokens.access, tokens.refresh, user.username)
    dispatch({ type: "SET_AUTHENTICATED", user, tokens })
  }, [])

  const register = useCallback(
    async (data: RegisterRequest) => {
      dispatch({ type: "SET_LOADING" })
      dispatch({ type: "SET_ERROR", error: null })

      const result = await safeFetch<{
        id: number
        username: string
        email: string
      }>(`${CONFIG.DJANGO_URL}/api/internal/accounts/register/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      })

      if (!result.ok) {
        dispatch({ type: "SET_ANONYMOUS" })
        dispatch({ type: "SET_ERROR", error: result.error })
        return
      }

      await login({ username: data.username, password: data.password1 })
    },
    [login],
  )

  const logout = useCallback(async () => {
    if (state.auth.status !== "authenticated") return

    const refreshToken = tokenStore.getRefresh()

    await safeFetch(`${CONFIG.DJANGO_URL}/api/internal/accounts/logout/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    })

    tokenStore.clear()
    dispatch({ type: "SET_ANONYMOUS" })
  }, [state.auth.status])

  const clearError = useCallback(() => {
    dispatch({ type: "SET_ERROR", error: null })
  }, [])

  return {
    auth: state.auth,
    error: state.error,
    login,
    register,
    logout,
    clearError,
  }
}
