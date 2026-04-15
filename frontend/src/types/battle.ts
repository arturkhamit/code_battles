export type BattlePhase =
  | "idle"
  | "creating"
  | "joining"
  | "lobby"
  | "active"
  | "finished"

export type BattleType = "1v1" | "group"

export type Language = "python" | "cpp"

export type SubmitStatus =
  | { kind: "none" }
  | { kind: "running" }
  | { kind: "accepted"; message: string }
  | { kind: "wrong"; message: string }
  | { kind: "error"; message: string }

export type LogEntry = {
  timestamp: string
  message: string
  level: "info" | "success" | "error" | "system" | "chat"
}

export type BattleState = {
  phase: BattlePhase
  battleId: number | null
  taskId: number
  battleType: BattleType
  duration: number
  maxParticipants: number
  deadline: number | null
  participantsCount: number
  submitStatus: SubmitStatus
  logs: LogEntry[]
  error: ApiErrorState | null
}

export type ApiErrorState = {
  message: string
  fieldErrors?: Record<string, string[]>
  isHtml?: boolean
}
