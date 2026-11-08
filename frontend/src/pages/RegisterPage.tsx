import { useState, type FormEvent } from "react"
import { Link, Navigate, useLocation } from "react-router-dom"
import { AuthShell, PasswordInput } from "../components/AuthShell"
import { ErrorBanner } from "../components/ErrorBanner"
import { Field } from "../components/ui/Field"
import { Icon } from "../components/ui/Icon"
import { useAuthContext } from "../hooks/auth-context"
import { usePageTitle } from "../hooks/use-page-title"
import { btn, describedBy, inputClass } from "../lib/ui"

// the server's rules (backend/apps/accounts/serializers/register.py + Django's validators)
const rules = (password: string) => [
  { ok: password.length >= 8, text: "At least 8 characters" },
  { ok: password.length > 0 && !/^\d+$/.test(password), text: "Not only digits" },
  { ok: null, text: "Not a common password, not close to your username or email" },
]

const Rule = ({ ok, text }: { ok: boolean | null; text: string }) => (
  <li className={`flex items-center gap-1.5 ${ok ? "text-main" : "text-sub"}`}>
    <Icon name={ok ? "check" : "dot"} className="h-3.5 w-3.5" />
    {text}
    {ok && <span className="sr-only">(done)</span>}
  </li>
)

export const RegisterPage = () => {
  usePageTitle("Create an account")
  const { auth, error, register, clearError } = useAuthContext()
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [password2, setPassword2] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const isLoading = auth.status === "loading"
  const busy = isLoading && submitted
  const mismatch = password2.length > 0 && password !== password2
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? "/training"

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (isLoading || mismatch) return
    setSubmitted(true)
    register({ username: username.trim(), email: email.trim(), password1: password, password2 })
  }

  if (auth.status === "authenticated") return <Navigate to={from} replace />

  const fields = error?.fieldErrors ?? {}
  const known = ["username", "email", "password1", "password2"]
  const general = error && !known.some((k) => fields[k]) ? error : null
  const password2Errors = mismatch ? ["The passwords do not match."] : fields.password2

  return (
    <AuthShell
      title="Create an account"
      subtitle="It takes a minute. No email confirmation."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" state={location.state} className="font-medium text-text underline-offset-4 hover:underline">
            Sign in
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
        <Field id="username" label="Username" errors={fields.username} help="Shown to other players. Letters, digits and @ . + - _">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            disabled={busy}
            autoComplete="username"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            maxLength={150}
            required
            className={inputClass}
            {...describedBy("username", true, fields.username)}
          />
        </Field>
        <Field id="email" label="Email" errors={fields.email}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={busy}
            autoComplete="email"
            inputMode="email"
            required
            className={inputClass}
            {...describedBy("email", false, fields.email)}
          />
        </Field>
        <Field
          id="password"
          label="Password"
          errors={fields.password1}
          help={
            <ul className="flex flex-col gap-0.5">
              {rules(password).map((r) => (
                <Rule key={r.text} ok={r.ok} text={r.text} />
              ))}
            </ul>
          }
        >
          <PasswordInput
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoComplete="new-password"
            required
            minLength={8}
            {...describedBy("password", true, fields.password1)}
          />
        </Field>
        <Field id="password2" label="Confirm password" errors={password2Errors}>
          <PasswordInput
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            disabled={busy}
            autoComplete="new-password"
            required
            {...describedBy("password2", false, password2Errors)}
          />
        </Field>
        <button type="submit" disabled={isLoading || mismatch} className={`${btn.primary} mt-2 w-full`}>
          {busy ? "Signing up…" : "Sign up"}
        </button>
      </form>
    </AuthShell>
  )
}
