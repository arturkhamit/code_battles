import { useEffect, useRef, useState } from "react"
import type { BattlePhase, LogEntry } from "../types/battle"

type LogPanelProps = {
  logs: LogEntry[]
  phase: BattlePhase
  onSendChat: (message: string) => void
}

const logLevelClass: Record<LogEntry["level"], string> = {
  info: "text-ctp-subtext1",
  success: "text-ctp-green",
  error: "text-ctp-red",
  system: "text-ctp-yellow",
  chat: "text-ctp-lavender",
}

export const LogPanel = ({ logs, phase, onSendChat }: LogPanelProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [chatInput, setChatInput] = useState("")

  const canChat = phase === "lobby" || phase === "active"

  useEffect(() => {
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const handleSubmit = () => {
    const trimmed = chatInput.trim()
    if (!trimmed) return
    onSendChat(trimmed)
    setChatInput("")
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <section
      className="flex flex-[0.8] flex-col overflow-hidden rounded-xl bg-ctp-surface0 p-4 shadow-lg"
      aria-label="Broadcast log and chat"
    >
      <h3 className="mb-2 text-sm font-semibold">Broadcasting</h3>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto rounded bg-ctp-crust p-2 font-mono text-xs"
        role="log"
        aria-live="polite"
      >
        {logs.map((entry, i) => (
          <div
            key={i}
            className={`${logLevelClass[entry.level]} whitespace-pre-wrap`}
          >
            [{entry.timestamp}] {entry.message}
          </div>
        ))}
      </div>

      {canChat && (
        <div className="mt-2 flex gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            maxLength={500}
            className="flex-1 rounded border border-ctp-surface1 bg-ctp-crust px-2 py-1.5 text-xs text-ctp-text outline-none transition placeholder:text-ctp-overlay0 focus:border-ctp-lavender"
            aria-label="Chat message input"
            tabIndex={0}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!chatInput.trim()}
            className="rounded bg-ctp-lavender px-3 py-1.5 text-xs font-bold text-ctp-crust transition hover:bg-ctp-blue disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
            aria-label="Send chat message"
            tabIndex={0}
          >
            Send
          </button>
        </div>
      )}
    </section>
  )
}
