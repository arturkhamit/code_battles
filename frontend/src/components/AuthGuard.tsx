import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuthContext } from "../hooks/auth-context"

export const AuthGuard = () => {
  const { auth } = useAuthContext()
  const location = useLocation()

  if (auth.status === "loading") {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-bg" aria-busy="true">
        <div className="text-center">
          <div className="mb-2 font-mono text-lg font-bold text-text">codebattles</div>
          <p className="text-sm text-sub">Loading your session…</p>
        </div>
      </div>
    )
  }

  if (auth.status === "anonymous") {
    // come back here after signing in (an invite link, a battle, a filtered catalog)
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }

  return <Outlet />
}
