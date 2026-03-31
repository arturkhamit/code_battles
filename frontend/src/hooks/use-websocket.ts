import { useCallback, useRef } from "react"
import { CONFIG } from "../config"
import { safeParseJson } from "../lib/api"
import type { WsClientMessage, WsServerEvent } from "../types/ws"

type UseWebSocketOptions = {
  onEvent: (event: WsServerEvent) => void
  onOpen: () => void
  onClose: (wasClean: boolean) => void
  onError: (message: string) => void
  shouldReconnect: () => boolean
}

export const useWebSocket = (options: UseWebSocketOptions) => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const intentionalCloseRef = useRef(false)
  const connectionParamsRef = useRef<{
    battleId: number
    userId: number
  } | null>(null)

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const connect = useCallback(
    (battleId: number, userId: number) => {
      clearReconnectTimer()
      intentionalCloseRef.current = false
      connectionParamsRef.current = { battleId, userId }

      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }

      const wsUrl = `${CONFIG.WS_URL}/ws/battle/${battleId}/${userId}`

      try {
        const socket = new WebSocket(wsUrl)
        wsRef.current = socket

        socket.onopen = () => {
          reconnectAttemptsRef.current = 0
          options.onOpen()
        }

        socket.onmessage = (event) => {
          try {
            const parsed = safeParseJson(
              typeof event.data === "string"
                ? event.data
                : JSON.stringify(event.data),
            )

            if (!parsed.ok) {
              options.onError(`Malformed message from server: ${parsed.error}`)
              return
            }

            const data = parsed.data as WsServerEvent
            if (!data || typeof data !== "object" || !("event" in data)) {
              options.onError("Received message without event field")
              return
            }

            options.onEvent(data)
          } catch (err) {
            options.onError(
              `Error processing message: ${err instanceof Error ? err.message : "Unknown"}`,
            )
          }
        }

        socket.onerror = () => {
          options.onError("WebSocket connection error")
        }

        socket.onclose = (event) => {
          wsRef.current = null
          const wasClean = event.wasClean || intentionalCloseRef.current

          if (!wasClean && options.shouldReconnect()) {
            attemptReconnect()
          }

          options.onClose(wasClean)
        }
      } catch (err) {
        options.onError(
          `Failed to create WebSocket: ${err instanceof Error ? err.message : "Unknown error"}`,
        )
      }
    },
    [options, clearReconnectTimer],
  )

  const attemptReconnect = useCallback(() => {
    const params = connectionParamsRef.current
    if (!params) return

    if (
      reconnectAttemptsRef.current >= CONFIG.WS_RECONNECT_MAX_ATTEMPTS
    ) {
      options.onError(
        `Reconnection failed after ${CONFIG.WS_RECONNECT_MAX_ATTEMPTS} attempts`,
      )
      return
    }

    reconnectAttemptsRef.current += 1
    const delay =
      CONFIG.WS_RECONNECT_BASE_MS *
      Math.pow(2, reconnectAttemptsRef.current - 1)

    options.onError(
      `Connection lost. Reconnecting in ${Math.round(delay / 1000)}s (attempt ${reconnectAttemptsRef.current}/${CONFIG.WS_RECONNECT_MAX_ATTEMPTS})...`,
    )

    reconnectTimerRef.current = setTimeout(() => {
      if (options.shouldReconnect()) {
        connect(params.battleId, params.userId)
      }
    }, delay)
  }, [options, connect])

  const send = useCallback(
    (message: WsClientMessage): boolean => {
      const socket = wsRef.current
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        options.onError("Cannot send message: WebSocket is not connected")
        return false
      }

      try {
        socket.send(JSON.stringify(message))
        return true
      } catch (err) {
        options.onError(
          `Failed to send message: ${err instanceof Error ? err.message : "Unknown"}`,
        )
        return false
      }
    },
    [options],
  )

  const disconnect = useCallback(() => {
    clearReconnectTimer()
    intentionalCloseRef.current = true
    connectionParamsRef.current = null
    reconnectAttemptsRef.current = 0

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [clearReconnectTimer])

  const isConnected = useCallback(
    () =>
      wsRef.current !== null &&
      wsRef.current.readyState === WebSocket.OPEN,
    [],
  )

  return { connect, disconnect, send, isConnected }
}
