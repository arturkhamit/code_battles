import type { ReactNode } from "react"
import { AuthContext } from "./auth-context"
import { useAuth } from "./use-auth"

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const auth = useAuth()
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
}
