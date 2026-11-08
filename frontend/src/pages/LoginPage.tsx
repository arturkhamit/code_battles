import { useState, type FormEvent } from "react"
import { Link, Navigate, useLocation } from "react-router-dom"
import { AuthShell, PasswordInput } from "../components/AuthShell"
import { ErrorBanner } from "../components/ErrorBanner"
import { Field } from "../components/ui/Field"
import { useAuthContext } from "../hooks/auth-context"
import { usePageTitle } from "../hooks/use-page-title"
import { btn, describedBy, inputClass } from "../lib/ui"

export const LoginPage = () => {
  usePageTitle("Sign in")
  const { auth, error, login, clearError } = useAuthContext()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const isLoading = auth.status === "loading"
  const busy = isLoading && submitted
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? "/training"

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (isLoading) return
    setSubmitted(true)
    login({ username: username.trim(), password })
  }

  if (auth.status === "authenticated") return <Navigate to={from} replace />

  const fields = error?.fieldErrors ?? {}
  const general = error && !fields.username && !fields.password ? error : null

  return (
    <AuthShell
      title="Sign in"
      subtitle="Solve problems and race other players."
      footer={
        <>
          New here?{" "}
          <Link to="/register" state={location.state} className="font-medium text-text underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      {general && (
        <div className="mt-4">
          <ErrorBanner error={general} onDismiss={clearError} />
        </div>
      )}
      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <Field id="username" label="Username" errors={fields.username}>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={busy}
            autoComplete="username"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            required
            className={inputClass}
            {...describedBy("username", false, fields.username)}
          />
        </Field>
        <Field id="password" label="Password" errors={fields.password}>
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoComplete="current-password"
            required
            {...describedBy("password", false, fields.password)}
          />
        </Field>
        <button type="submit" disabled={isLoading} className={`${btn.primary} mt-2 w-full`} aria-label="Sign in">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </AuthShell>
  )
}
