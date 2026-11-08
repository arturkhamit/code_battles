import { useEffect, useRef, useState, type FormEvent } from "react"
import { inputClass } from "../lib/ui"
import type { BattlePhase, LogEntry } from "../types/battle"
import { Icon } from "./ui/Icon"

type LogPanelProps = {
  logs: LogEntry[]
  phase: BattlePhase
  onSendChat: (message: string) => void
}

const logLevelClass: Record<LogEntry["level"], string> = {
  info: "text-sub",
  success: "text-main",
  error: "text-error",
  system: "text-yellow",
  chat: "text-accent",
}

export const LogPanel = ({ logs, phase, onSendChat }: LogPanelProps) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [chatInput, setChatInput] = useState("")
  const canChat = phase === "lobby" || phase === "active"

  useEffect(() => {
    const el = containerRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    const trimmed = chatInput.trim()
    if (!trimmed) return
    onSendChat(trimmed)
    setChatInput("")
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2" aria-label="Battle log and chat">
      <div ref={containerRef} className="min-h-40 flex-1 overflow-y-auto overscroll-contain rounded-lg bg-bg p-3 font-mono text-xs leading-5" role="log" aria-live="polite">
        {logs.length === 0 && <p className="text-sub">Events and chat appear here.</p>}
        {logs.map((entry, i) => (
          <div key={i} className={`${logLevelClass[entry.level]} break-words whitespace-pre-wrap`}>
            <span className="num text-sub">{entry.timestamp}</span> {entry.message}
          </div>
        ))}
      </div>

      {canChat && (
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Message everyone"
            maxLength={1000}
            className={inputClass}
            aria-label="Chat message input"
            enterKeyHint="send"
          />
          <button
            type="submit"
            disabled={!chatInput.trim()}
            className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-lg border border-input-border bg-input-bg text-sub transition hover:text-text disabled:opacity-40 pointer-coarse:min-h-11 pointer-coarse:min-w-11"
            aria-label="Send chat message"
          >
            <Icon name="send" />
          </button>
        </form>
      )}
    </div>
  )
}
