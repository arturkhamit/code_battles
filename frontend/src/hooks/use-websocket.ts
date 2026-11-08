import { useCallback, useEffect, useRef } from "react"
import { CONFIG } from "../config"
import { safeParseJson } from "../lib/api"
import { getFreshAccess, tokenStore } from "../lib/token-store"
import type { WsClientMessage, WsServerEvent } from "../types/ws"

// Server refusals: retrying cannot help (see fastapi_app/api/routers/websockets.py)
const FINAL_CLOSE_CODES = new Set([1000, 1008, 4001, 4400, 4403, 4404, 4409, 4429])

/** retryIn: ms until the next attempt, or null when the socket is gone for good. */
export type WsCloseInfo = { code: number; retryIn: number | null }

export type WsTarget = { battleId: number; role?: string; invite?: string }

type UseWebSocketOptions = {
  onEvent: (event: WsServerEvent) => void
  onClose: (info: WsCloseInfo) => void
}

// Same origin by default: ws: on http, wss: on https
const wsBaseUrl = () =>
  CONFIG.WS_URL || `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}`

export const useWebSocket = (options: UseWebSocketOptions) => {
  const optionsRef = useRef(options)
  useEffect(() => {
    optionsRef.current = options
  })

  const wsRef = useRef<WebSocket | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // bumped by every connect/disconnect: a late async step of an older connect sees it and stops
  const generationRef = useRef(0)

  const disconnect = useCallback(() => {
    generationRef.current += 1
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    const socket = wsRef.current
    wsRef.current = null // its onclose sees this and stays quiet
    socket?.close(1000)
  }, [])

  const connect = useCallback(
    (target: WsTarget) => {
      disconnect()
      const generation = generationRef.current
      let attempts = 0

      const run = async () => {
        // a fresh access token for every attempt: the old one may have expired meanwhile
        const token = (await getFreshAccess()) ?? tokenStore.getAccess()
        if (generation !== generationRef.current) return
        if (!token) {
          optionsRef.current.onClose({ code: 1008, retryIn: null })
          return
        }

        const query = new URLSearchParams({ token })
        if (target.role) query.set("role", target.role)
        if (target.invite) query.set("invite", target.invite)
        const socket = new WebSocket(`${wsBaseUrl()}/ws/battle/${target.battleId}?${query}`)
        wsRef.current = socket

        socket.onmessage = (message) => {
          if (wsRef.current !== socket) return
          const parsed = safeParseJson(typeof message.data === "string" ? message.data : "")
          const data = parsed.ok ? parsed.data : null
          if (!data || typeof data !== "object" || !("event" in data)) {
            console.debug("Ignoring a malformed WS frame", message.data)
            return
          }
          attempts = 0 // the server talks to us: a later drop starts the backoff anew
          optionsRef.current.onEvent(data as WsServerEvent)
        }

        socket.onclose = (event) => {
          if (wsRef.current !== socket) return // closed by us
          wsRef.current = null
          if (FINAL_CLOSE_CODES.has(event.code) || attempts >= CONFIG.WS_RECONNECT_MAX_ATTEMPTS) {
            optionsRef.current.onClose({ code: event.code, retryIn: null })
            return
          }
          // network drop (1006), server restart (1001) or outage (1011): back off and retry
          const delay = CONFIG.WS_RECONNECT_BASE_MS * 2 ** attempts
          attempts += 1
          optionsRef.current.onClose({ code: event.code, retryIn: delay })
          timerRef.current = setTimeout(run, delay)
        }
      }

      void run()
    },
    [disconnect],
  )

  const send = useCallback((message: WsClientMessage): boolean => {
    const socket = wsRef.current
    if (!socket || socket.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(message))
    return true
  }, [])

  // leaving the page (also through logout: the guard unmounts it) closes the socket
  useEffect(() => disconnect, [disconnect])

  return { connect, disconnect, send }
}
