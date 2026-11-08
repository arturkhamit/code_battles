import { CONFIG } from "../config"
import type {
  BattleType,
  CreateBattleParams,
  CreatedBattle,
  InviteInfo,
  OpenBattle,
  Page,
} from "../types/battle"
import { authFetch } from "./token-store"

export const createBattle = (params: CreateBattleParams) =>
  authFetch<CreatedBattle>(`${CONFIG.DJANGO_URL}/api/battles/create/`, {
    method: "POST",
    body: JSON.stringify(params),
  })

export const fetchOpenBattles = (limit: number, offset: number) =>
  authFetch<Page<OpenBattle>>(
    `${CONFIG.DJANGO_URL}/api/battles/open/?limit=${limit}&offset=${offset}`,
  )

export const resolveInvite = (code: string) =>
  authFetch<InviteInfo>(
    `${CONFIG.DJANGO_URL}/api/battles/invite/${encodeURIComponent(code)}/`,
  )

// What this browser knows about a battle before its socket joins: the invite code, plus the task
// and type as a head start (role_assigned is the source of truth for them).
export type KnownBattle = {
  invite?: string
  task?: number
  type?: BattleType
}

const KNOWN_KEY = "cb_battles"
const KNOWN_MAX = 50

const readKnown = (): Record<string, KnownBattle> => {
  try {
    return JSON.parse(localStorage.getItem(KNOWN_KEY) ?? "{}") ?? {}
  } catch {
    return {}
  }
}

export const getKnownBattle = (id: number): KnownBattle => readKnown()[id] ?? {}

export const rememberBattle = (id: number, info: KnownBattle) => {
  const all = readKnown()
  const merged = { ...all[id], ...info }
  delete all[id]
  // insertion order = age: keep the newest KNOWN_MAX entries
  const entries = [...Object.entries(all), [String(id), merged] as const].slice(-KNOWN_MAX)
  try {
    localStorage.setItem(KNOWN_KEY, JSON.stringify(Object.fromEntries(entries)))
  } catch {
    // storage full or blocked: the page still works, the server sends all of it on join
  }
}

/** Link that lets someone else into the battle (the code is needed for a private one). */
export const battleLink = (id: number, invite?: string) =>
  `${location.origin}/battle/${id}${invite ? `?invite=${encodeURIComponent(invite)}` : ""}`

// WS close codes the server uses; none of them is retried
export const CLOSE_MESSAGES: Record<number, string> = {
  1008: "Your session has expired. Please sign in again.",
  4001: "This battle is open in another tab. Continue there, or reload this page to move it here.",
  4400: "The battle link is invalid.",
  4403: "This battle is private: you need an invite link to join.",
  4404: "This battle does not exist.",
  4409: "You cannot join as a player: the battle is full, already started or finished.",
  4429: "Too many connection attempts. Wait a minute and reload the page.",
}

export const ERROR_MESSAGES: Record<string, string> = {
  invalid_json: "The server could not read the message.",
  invalid_message: "The server rejected the message.",
  message_too_large: "The message is too large.",
  code_too_large: "Your code is too long (64 KiB at most).",
  message_too_long: "The chat message is too long (1000 characters at most).",
  spectator_forbidden: "Spectators can only watch.",
  battle_over: "The battle is over.",
  battle_not_active: "The battle has not started yet.",
  conflict: "The battle has already started.",
  forbidden: "Only the creator of the battle can start it.",
  not_found: "The battle was not found.",
  bad_request: "The battle cannot start yet: it needs at least 2 players.",
  service_unavailable: "The game service is temporarily unavailable. Try again shortly.",
  service_error: "The game service failed. Try again.",
  task_unavailable: "The task of this battle could not be loaded.",
  rate_limited: "Too many requests.",
  internal_error: "Server error, try again.",
}

export const describeWsError = (code: string, message: string, retryAfter?: number) => {
  const text = ERROR_MESSAGES[code] ?? message
  return retryAfter ? `${text} Try again in ${retryAfter} s.` : text
}
