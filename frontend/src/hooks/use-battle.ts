import { useCallback, useEffect, useReducer, useState } from "react"
import { CONFIG } from "../config"
import {
  CLOSE_MESSAGES,
  describeWsError,
  getKnownBattle,
  rememberBattle,
  resolveInvite,
} from "../lib/battles"
import { authFetch } from "../lib/token-store"
import { verdictStatus } from "../lib/verdict"
import type {
  BattleFacts,
  BattlePhase,
  BattleResult,
  BattleState,
  Language,
  LogEntry,
  SubmitStatus,
} from "../types/battle"
import type { TaskInfo } from "../types/task"
import type { WsServerEvent } from "../types/ws"
import { useTimer } from "./use-timer"
import { useWebSocket, type WsCloseInfo, type WsTarget } from "./use-websocket"

const MAX_LOGS = 500

type Action =
  | { type: "LOG"; entry: LogEntry }
  | { type: "JOINED"; isSpectator: boolean; isCreator: boolean; count: number; facts: BattleFacts }
  | { type: "FINISHED"; result: BattleResult }
  | { type: "PARTICIPANTS"; count: number }
  | { type: "TASK"; taskId: number }
  | { type: "PHASE"; phase: BattlePhase }
  | { type: "SUBMIT"; status: SubmitStatus }
  | { type: "WS_ERROR"; message: string }
  | { type: "CLOSED"; code: number; message: string }
  | { type: "CLEAR_ERROR" }

const reducer = (state: BattleState, action: Action): BattleState => {
  switch (action.type) {
    case "LOG":
      return { ...state, logs: [...state.logs, action.entry].slice(-MAX_LOGS) }
    case "JOINED":
      return {
        ...state,
        isSpectator: action.isSpectator,
        isCreator: action.isCreator,
        participantsCount: action.count,
        facts: action.facts,
        phase: state.phase === "connecting" ? "lobby" : state.phase,
      }
    case "FINISHED":
      return { ...state, phase: "finished", result: action.result }
    case "PARTICIPANTS":
      return { ...state, participantsCount: action.count }
    case "TASK":
      return { ...state, taskId: action.taskId }
    case "PHASE":
      return { ...state, phase: action.phase }
    case "SUBMIT":
      return { ...state, submitStatus: action.status }
    case "WS_ERROR":
      return {
        ...state,
        error: { message: action.message },
        // the error answers the submission in flight
        submitStatus:
          state.submitStatus.kind === "running"
            ? { kind: "error", message: action.message }
            : state.submitStatus,
      }
    case "CLOSED":
      return {
        ...state,
        closed: { code: action.code, message: action.message },
        phase: state.phase === "finished" ? "finished" : "closed",
      }
    case "CLEAR_ERROR":
      return { ...state, error: null }
    default:
      return state
  }
}

const initState = (battleId: number): BattleState => ({
  phase: "connecting",
  taskId: getKnownBattle(battleId).task ?? null,
  participantsCount: null,
  isSpectator: false,
  isCreator: false,
  submitStatus: { kind: "none" },
  logs: [],
  error: null,
  closed: null,
  facts: null,
  result: null,
})

/** One battle, from mount to unmount: BattlePage remounts it (key) for another battle or role. */
export const useBattle = (target: WsTarget, userId: number) => {
  const { battleId } = target
  const [state, dispatch] = useReducer(reducer, battleId, initState)
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null)
  const timer = useTimer()
  const { start: startTimer, stop: stopTimer } = timer

  const addLog = useCallback((message: string, level: LogEntry["level"] = "info") => {
    dispatch({
      type: "LOG",
      entry: { timestamp: new Date().toLocaleTimeString(), message, level },
    })
  }, [])

  const handleEvent = useCallback(
    (event: WsServerEvent) => {
      switch (event.event) {
        case "role_assigned": {
          const { role, is_creator, players_count, task_id, type } = event.data
          const spectating = role === "spectator"
          dispatch({
            type: "JOINED",
            isSpectator: spectating,
            isCreator: is_creator,
            count: players_count,
            facts: {
              type,
              maxParticipants: event.data.max_participants,
              creatorName: event.data.creator_username ?? null,
              durationMinutes: event.data.duration ?? null,
            },
          })
          if (typeof task_id === "number") {
            dispatch({ type: "TASK", taskId: task_id })
            rememberBattle(battleId, { task: task_id, type })
          }
          addLog(spectating ? "You joined as a spectator (watch only)." : "You joined as a player.", "system")
          break
        }
        case "lobby_update": {
          dispatch({ type: "PARTICIPANTS", count: event.data.participants_count })
          if (typeof event.data.task_id === "number") {
            dispatch({ type: "TASK", taskId: event.data.task_id })
            rememberBattle(battleId, { task: event.data.task_id })
          }
          break
        }
        case "battle_started": {
          dispatch({ type: "PHASE", phase: "active" })
          startTimer(event.data.remaining_seconds)
          addLog("Battle is running. Good luck!", "success")
          break
        }
        case "battle_finished": {
          stopTimer()
          const { winner_id, winner_username, reason } = event.data
          dispatch({ type: "FINISHED", result: { winnerId: winner_id, winnerName: winner_username, reason } })
          let message: string
          if (winner_id === null) {
            message = reason === "time_up" ? "Time is up: a draw." : "Battle finished: a draw."
          } else if (winner_id === userId) {
            message = "You won!"
          } else {
            message = `Winner: ${winner_username ?? `user ${winner_id}`}`
          }
          addLog(`Battle finished. ${message}`, winner_id === userId ? "success" : "system")
          dispatch({
            type: "SUBMIT",
            status: winner_id === userId ? { kind: "accepted", message } : { kind: "error", message },
          })
          break
        }
        case "execution_result": {
          const status = verdictStatus(event.data)
          dispatch({ type: "SUBMIT", status })
          if (status.kind === "accepted") addLog("All tests passed!", "success")
          else if (status.kind === "wrong") addLog(`Your submission: ${status.message}.`, "error")
          break
        }
        case "opponent_running_code": {
          if (event.data.user_id !== userId) {
            addLog(`Opponent ${event.data.username} is running code...`, "system")
          }
          break
        }
        case "user_joined": {
          if (event.data.user_id !== userId) {
            addLog(`${event.data.username} joined as ${event.data.role}.`, "system")
          }
          break
        }
        case "user_left": {
          if (event.data.user_id !== userId) {
            addLog(`${event.data.username} left.`, "info")
          }
          break
        }
        case "chat_message": {
          addLog(`${event.data.username}: ${event.data.message}`, "chat")
          break
        }
        case "error": {
          const message = describeWsError(event.data.code, event.data.message, event.data.retry_after)
          dispatch({ type: "WS_ERROR", message })
          addLog(message, "error")
          break
        }
        default:
          console.debug("Ignoring unknown WS event", event)
      }
    },
    [addLog, startTimer, stopTimer, userId, battleId],
  )

  const handleClose = useCallback(
    ({ code, retryIn }: WsCloseInfo) => {
      if (retryIn !== null) {
        addLog(`Connection lost. Reconnecting in ${Math.round(retryIn / 1000)} s...`, "error")
        return
      }
      stopTimer()
      const message =
        CLOSE_MESSAGES[code] ??
        (code === 1011
          ? "The game service is unavailable. Reload the page later."
          : "Disconnected from the battle. Reload the page to reconnect.")
      dispatch({ type: "CLOSED", code, message })
      addLog(message, "error")
    },
    [addLog, stopTimer],
  )

  const { connect, disconnect, send } = useWebSocket({ onEvent: handleEvent, onClose: handleClose })
  const { role, invite } = target

  useEffect(() => {
    connect({ battleId, role, invite })
    return disconnect
  }, [connect, disconnect, battleId, role, invite])

  // Only a head start: role_assigned names the task anyway, the invite code just knows it sooner.
  useEffect(() => {
    if (!invite || getKnownBattle(battleId).task) return
    let cancelled = false
    resolveInvite(invite).then((result) => {
      if (cancelled || !result.ok || result.data.id !== battleId) return
      dispatch({ type: "TASK", taskId: result.data.task.id })
      rememberBattle(battleId, { task: result.data.task.id, type: result.data.type })
    })
    return () => {
      cancelled = true
    }
  }, [battleId, invite])

  useEffect(() => {
    if (state.taskId === null) return
    let cancelled = false
    authFetch<TaskInfo>(`${CONFIG.FASTAPI_URL}/api/tasks/${state.taskId}/info`).then((result) => {
      if (cancelled) return
      if (result.ok) setTaskInfo(result.data)
      else addLog(`Failed to load the task: ${result.error.message}`, "error")
    })
    return () => {
      cancelled = true
    }
  }, [state.taskId, addLog])

  const handleStart = useCallback(() => {
    if (send({ action: "start_battle_request" })) {
      addLog("Asking the server to start the battle...", "system")
    } else {
      addLog("Not connected to the battle.", "error")
    }
  }, [send, addLog])

  const handleSubmit = useCallback(
    (code: string, language: Language) => {
      if (send({ action: "submit_code", language, code })) {
        dispatch({ type: "SUBMIT", status: { kind: "running" } })
        addLog("Code submitted...", "system")
      } else {
        dispatch({ type: "SUBMIT", status: { kind: "error", message: "Not connected: code not sent." } })
      }
    },
    [send, addLog],
  )

  const handleChat = useCallback(
    (message: string) => {
      const trimmed = message.trim()
      if (trimmed && !send({ action: "send_chat", message: trimmed })) {
        addLog("Not connected: message not sent.", "error")
      }
    },
    [send, addLog],
  )

  const clearError = useCallback(() => dispatch({ type: "CLEAR_ERROR" }), [])

  return { state, taskInfo, timer, handleStart, handleSubmit, handleChat, clearError }
}
