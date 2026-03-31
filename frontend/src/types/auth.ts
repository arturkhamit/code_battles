export type AuthUser = {
  id: number
  username: string
  email: string
}

export type AuthTokens = {
  access: string
  refresh: string
}

export type LoginRequest = {
  username: string
  password: string
}

export type RegisterRequest = {
  username: string
  email: string
  password1: string
  password2: string
}

export type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: AuthUser; tokens: AuthTokens }
