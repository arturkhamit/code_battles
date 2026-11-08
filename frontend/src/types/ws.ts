import type { BattleType, Language } from "./battle"

export type WsClientMessage =
  | { action: "start_battle_request" }
  // the server judges the battle's own task: no task_id here
  | { action: "submit_code"; language: Language; code: string }
  | { action: "send_chat"; message: string }

export type WsRole = "player" | "spectator"

// verdict: accepted | wrong_answer | time_limit | runtime_error | memory_limit | compile_error | error
// `message` is always a readable sentence ("Time limit exceeded on test case #3"); `details` is the
// compiler log, or input / expected / output / stderr of a public test. A hidden test is only a number.
export type ExecutionResult = {
  status: string
  is_correct: boolean
  verdict: string
  message: string
  details?: string
  test_number?: number
  hidden?: boolean
  passed?: number
  total?: number
  time_ms?: number
  memory_mb?: number
}

// The first event of a socket, from the server's join: the source of truth for the lobby
export type WsRoleAssigned = {
  role: WsRole
  battle_id: number
  task_id: number | null
  type: BattleType
  battle_status: "pending" | "active" | "finished"
  players_count: number
  max_participants: number
  creator_id: number
  is_creator: boolean
  creator_username?: string | null
  duration?: number | null // minutes
}

export type WsServerEvent =
  | { event: "role_assigned"; data: WsRoleAssigned }
  | { event: "user_joined"; data: { user_id: number; username: string; role: WsRole } }
  | { event: "user_left"; data: { user_id: number; username: string } }
  | { event: "lobby_update"; data: { participants_count: number; task_id?: number } }
  | { event: "battle_started"; data: { deadline: number; remaining_seconds: number } }
  | { event: "opponent_running_code"; data: { user_id: number; username: string } }
  | { event: "execution_result"; data: ExecutionResult }
  | {
      event: "battle_finished"
      data: {
        winner_id: number | null
        winner_username: string | null
        reason: "solved" | "time_up"
      }
    }
  | { event: "chat_message"; data: { user_id: number; username: string; message: string } }
  | { event: "error"; data: { code: string; message: string; retry_after?: number } }
