import { createContext, useContext } from "react"
import type { useAuth } from "./use-auth"

type AuthContextValue = ReturnType<typeof useAuth>

export const AuthContext = createContext<AuthContextValue | null>(null)

export const useAuthContext = (): AuthContextValue => {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error("useAuthContext must be used within AuthProvider")
  }
  return ctx
}
