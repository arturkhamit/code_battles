import type { ReactNode } from "react"
import { useAuth } from "../hooks/use-auth"
import { AuthForm } from "./AuthForm"

type AuthGuardProps = {
  children: (props: {
    userId: number
    username: string
    onLogout: () => void
  }) => ReactNode
}

export const AuthGuard = ({ children }: AuthGuardProps) => {
  const { auth, error, login, register, logout, clearError } = useAuth()

  if (auth.status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ctp-base">
        <div className="text-center">
          <div className="mb-2 text-lg font-semibold text-ctp-blue">
            Code Battle Arena
          </div>
          <p className="text-sm text-ctp-subtext0">Loading session...</p>
        </div>
      </div>
    )
  }

  if (auth.status === "anonymous") {
    return (
      <AuthForm
        isLoading={false}
        error={error}
        onLogin={login}
        onRegister={register}
        onClearError={clearError}
      />
    )
  }

  return (
    <>
      {children({
        userId: auth.user.id,
        username: auth.user.username,
        onLogout: logout,
      })}
    </>
  )
}
