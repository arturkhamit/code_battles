export type BattlePhase =
  | "connecting"
  | "lobby"
  | "active"
  | "finished"
  | "closed"

export type BattleType = "1v1" | "group"

export type Language = "python" | "cpp"

export type SubmitStatus =
  | { kind: "none" }
  | { kind: "running" }
  | { kind: "accepted"; message: string; detail?: string }
  // stats: "3 of 10 tests passed · 120 ms"; detail: the compiler log or the failed public test
  | { kind: "wrong"; message: string; stats?: string; detail?: string }
  | { kind: "error"; message: string }

export type BattleResult = {
  winnerId: number | null
  winnerName: string | null
  reason: "solved" | "time_up"
}

// what the lobby header shows, from role_assigned
export type BattleFacts = {
  type: BattleType
  maxParticipants: number
  creatorName: string | null
  durationMinutes: number | null
}

export type LogEntry = {
  timestamp: string
  message: string
  level: "info" | "success" | "error" | "system" | "chat"
}

export type BattleState = {
  phase: BattlePhase
  taskId: number | null
  // players, from role_assigned and then lobby_update; null until the socket has joined
  participantsCount: number | null
  isSpectator: boolean
  isCreator: boolean
  submitStatus: SubmitStatus
  logs: LogEntry[]
  error: ApiErrorState | null
  // why the socket is gone for good (a close code that must not be retried)
  closed: { code: number; message: string } | null
  facts: BattleFacts | null
  result: BattleResult | null
}

export type ApiErrorState = {
  message: string
  fieldErrors?: Record<string, string[]>
  isHtml?: boolean
  status?: number
  retryAfter?: number
}

export type CreateBattleParams = {
  task: number
  type: BattleType
  duration: number
  max_participants?: number
  is_private: boolean
  ranked: boolean
}

export type CreatedBattle = {
  id: number
  type: BattleType
  task: number
  invite_code: string
  is_private: boolean
}

export type OpenBattle = {
  id: number
  type: BattleType
  task: { id: number; name: string | null; difficulty_label: string }
  duration: number
  max_participants: number
  players_count: number
  creator_username: string
  created_at: string
  invite_code: string
}

export type InviteInfo = {
  id: number
  type: BattleType
  status: string
  task: { id: number; name: string | null; difficulty_label: string }
  players_count: number
  max_participants: number
  is_private: boolean
}

export type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
