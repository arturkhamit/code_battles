import { useState, type InputHTMLAttributes, type ReactNode } from "react"
import { inputClass } from "../lib/ui"
import { Icon } from "./ui/Icon"

export const AuthShell = ({ title, subtitle, children, footer }: { title: string; subtitle: string; children: ReactNode; footer: ReactNode }) => (
  <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-bg px-4 py-8">
    <div className="flex items-center gap-2">
      <Icon name="logo" className="h-7 w-7 text-main" />
      <span className="font-mono text-2xl font-bold text-text">codebattles</span>
    </div>
    <main className="w-full max-w-sm rounded-2xl border border-card-border bg-sub-alt p-6 sm:p-8">
      <h1 className="text-xl font-semibold text-text">{title}</h1>
      <p className="mt-1 text-sm text-sub">{subtitle}</p>
      {children}
    </main>
    <p className="text-sm text-sub">{footer}</p>
  </div>
)

export const PasswordInput = (props: InputHTMLAttributes<HTMLInputElement>) => {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input {...props} type={show ? "text" : "password"} className={`${inputClass} pr-11`} />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        className="absolute top-1/2 right-1 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-sub transition hover:text-text"
        aria-label={show ? "Hide password" : "Show password"}
        aria-pressed={show}
      >
        <Icon name={show ? "eyeOff" : "eye"} className="h-5 w-5" />
      </button>
    </div>
  )
}
