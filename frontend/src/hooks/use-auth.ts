import { useCallback, useEffect, useReducer, useRef } from "react"
import { CONFIG } from "../config"
import { safeFetch } from "../lib/api"
import { decodeJwtPayload, getFreshAccess, tokenStore } from "../lib/token-store"
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

  // StrictMode runs effects twice in development: bootstrap once (refresh tokens are single-use).
  const bootstrapped = useRef(false)

  useEffect(() => {
    if (bootstrapped.current) return
    bootstrapped.current = true

    if (!tokenStore.getRefresh()) {
      dispatch({ type: "SET_ANONYMOUS" })
      return
    }
    // Refreshes only an expired access token. A network error or 5xx keeps the stored session;
    // a rejected refresh token clears the store.
    getFreshAccess().then(() => {
      const access = tokenStore.getAccess()
      const refresh = tokenStore.getRefresh()
      const tokens = access && refresh ? { access, refresh } : null
      const user = tokens && extractUserFromTokens(tokens, tokenStore.getUsername() ?? "")
      if (tokens && user) {
        dispatch({ type: "SET_AUTHENTICATED", user, tokens })
      } else {
        dispatch({ type: "SET_ANONYMOUS" })
      }
    })
  }, [])

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
      `${CONFIG.DJANGO_URL}/api/accounts/login/`,
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
      }>(`${CONFIG.DJANGO_URL}/api/accounts/register/`, {
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

    await safeFetch(`${CONFIG.DJANGO_URL}/api/accounts/logout/`, {
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
