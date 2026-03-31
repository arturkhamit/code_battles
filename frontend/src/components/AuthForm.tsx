import { useState, useCallback, type FormEvent } from "react"
import type { ApiErrorState } from "../types/battle"
import type { LoginRequest, RegisterRequest } from "../types/auth"
import { ErrorBanner } from "./ErrorBanner"

type AuthFormProps = {
  isLoading: boolean
  error: ApiErrorState | null
  onLogin: (data: LoginRequest) => void
  onRegister: (data: RegisterRequest) => void
  onClearError: () => void
}

type Mode = "login" | "register"

export const AuthForm = ({
  isLoading,
  error,
  onLogin,
  onRegister,
  onClearError,
}: AuthFormProps) => {
  const [mode, setMode] = useState<Mode>("login")
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [password2, setPassword2] = useState("")

  const handleToggleMode = useCallback(() => {
    setMode((prev) => (prev === "login" ? "register" : "login"))
    onClearError()
  }, [onClearError])

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      if (isLoading) return

      if (mode === "login") {
        onLogin({ username, password })
      } else {
        onRegister({
          username,
          email,
          password1: password,
          password2,
        })
      }
    },
    [mode, username, email, password, password2, isLoading, onLogin, onRegister],
  )

  const fieldHasError = (field: string) =>
    error?.fieldErrors?.[field]?.length ?? false

  const inputClass = (hasError: boolean | number) =>
    `w-full rounded border bg-ctp-crust px-3 py-2 text-sm text-ctp-text outline-none transition ${
      hasError
        ? "border-ctp-red ring-1 ring-ctp-red"
        : "border-ctp-surface1 focus:border-ctp-blue"
    }`

  return (
    <div className="flex min-h-screen items-center justify-center bg-ctp-base p-4">
      <div className="w-full max-w-sm rounded-xl bg-ctp-surface0 p-6 shadow-lg">
        <h1 className="mb-1 text-center text-2xl font-bold text-ctp-blue">
          Code Battle Arena
        </h1>
        <p className="mb-6 text-center text-sm text-ctp-subtext0">
          {mode === "login"
            ? "Sign in to your account"
            : "Create a new account"}
        </p>

        {error && <div className="mb-4"><ErrorBanner error={error} onDismiss={onClearError} /></div>}

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label
              htmlFor="auth-username"
              className="mb-1 block text-xs font-medium text-ctp-subtext1"
            >
              Username
            </label>
            <input
              id="auth-username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
              className={inputClass(fieldHasError("username"))}
              placeholder="Enter username"
              autoComplete="username"
              required
              aria-label="Username"
            />
          </div>

          {mode === "register" && (
            <div>
              <label
                htmlFor="auth-email"
                className="mb-1 block text-xs font-medium text-ctp-subtext1"
              >
                Email
              </label>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isLoading}
                className={inputClass(fieldHasError("email"))}
                placeholder="Enter email"
                autoComplete="email"
                required
                aria-label="Email"
              />
            </div>
          )}

          <div>
            <label
              htmlFor="auth-password"
              className="mb-1 block text-xs font-medium text-ctp-subtext1"
            >
              Password
            </label>
            <input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
              className={inputClass(
                fieldHasError("password") || fieldHasError("password1"),
              )}
              placeholder="Enter password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              required
              aria-label="Password"
            />
          </div>

          {mode === "register" && (
            <div>
              <label
                htmlFor="auth-password2"
                className="mb-1 block text-xs font-medium text-ctp-subtext1"
              >
                Confirm Password
              </label>
              <input
                id="auth-password2"
                type="password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                disabled={isLoading}
                className={inputClass(fieldHasError("password2"))}
                placeholder="Repeat password"
                autoComplete="new-password"
                required
                aria-label="Confirm password"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="mt-2 rounded bg-ctp-blue py-2.5 text-sm font-bold text-ctp-crust transition hover:bg-ctp-lavender disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
            aria-label={mode === "login" ? "Sign in" : "Create account"}
            tabIndex={0}
          >
            {isLoading
              ? "Please wait..."
              : mode === "login"
                ? "Sign In"
                : "Create Account"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={handleToggleMode}
            disabled={isLoading}
            className="text-sm text-ctp-blue transition hover:text-ctp-lavender hover:underline"
            tabIndex={0}
            aria-label={
              mode === "login"
                ? "Switch to register form"
                : "Switch to login form"
            }
          >
            {mode === "login"
              ? "Don't have an account? Register"
              : "Already have an account? Sign In"}
          </button>
        </div>
      </div>
    </div>
  )
}
