import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react"
import { btn } from "../lib/ui"
import type { BattlePhase, Language, SubmitStatus } from "../types/battle"
import { Icon } from "./ui/Icon"

type CodePanelProps = {
  phase: BattlePhase
  isSpectator: boolean
  submitStatus: SubmitStatus
  onSubmit: (code: string, language: Language) => void
  disabled?: boolean
  /** why submitting is off, said under the button (a cooldown, no task yet) */
  disabledReason?: string
  /** localStorage key of the draft; the panel remembers the code per task */
  draftKey?: string
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>
}

const INDENT = "    "
const LANG_KEY = "cb_language"

const read = (key: string) => {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
const write = (key: string, value: string) => {
  try {
    localStorage.setItem(key, value)
  } catch {
    // storage blocked: drafts are a convenience only
  }
}

const VerdictPanel = ({ status, isSpectator, idleText }: { status: SubmitStatus; isSpectator: boolean; idleText: string }) => {
  let tone = "border-input-border text-sub"
  let body: ReactNode = isSpectator ? "Spectating: you can watch, not submit." : idleText
  if (!isSpectator && status.kind === "running") {
    tone = "border-yellow/50 bg-yellow/5 text-yellow"
    body = "Running your code on the tests…"
  } else if (!isSpectator && status.kind === "accepted") {
    tone = "border-main/60 bg-main/10 text-main"
    body = (
      <>
        <span className="font-semibold">{status.message}</span>
        {status.detail && <span className="mt-0.5 block text-xs text-sub">{status.detail}</span>}
      </>
    )
  } else if (!isSpectator && status.kind === "wrong") {
    tone = "border-error/60 bg-error/10 text-error"
    body = (
      <>
        <span className="font-semibold">{status.message}</span>
        {status.stats && <span className="mt-0.5 block text-xs text-sub">{status.stats}</span>}
        {status.detail && (
          <pre className="mt-2 max-h-40 overflow-auto rounded bg-bg p-2 font-mono text-xs whitespace-pre-wrap text-text">
            {status.detail}
          </pre>
        )}
      </>
    )
  } else if (!isSpectator && status.kind === "error") {
    tone = "border-error/60 bg-error/10 text-error"
    body = <span className="whitespace-pre-wrap">{status.message}</span>
  }
  return (
    <div role="status" className={`rounded-lg border px-3 py-2 text-sm ${tone}`}>
      {body}
    </div>
  )
}

export const CodePanel = ({
  phase,
  isSpectator,
  submitStatus,
  onSubmit,
  disabled = false,
  disabledReason,
  draftKey,
  textareaRef,
}: CodePanelProps) => {
  const [code, setCode] = useState(() => (draftKey ? read(draftKey) ?? "" : ""))
  const [language, setLanguage] = useState<Language>(() => (read(LANG_KEY) === "cpp" ? "cpp" : "python"))
  const tabMovesFocus = useRef(false)

  useEffect(() => {
    if (!draftKey) return
    const t = setTimeout(() => write(draftKey, code), 400)
    return () => clearTimeout(t)
  }, [code, draftKey])

  const canEdit = phase === "active" && !isSpectator
  const running = submitStatus.kind === "running"
  const canSubmit = canEdit && !disabled && !running && code.trim() !== ""

  const submit = useCallback(() => {
    if (canSubmit) onSubmit(code, language)
  }, [canSubmit, code, language, onSubmit])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    const el = e.currentTarget
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault()
      submit()
      return
    }
    if (e.key === "Escape") {
      tabMovesFocus.current = true // Esc, then Tab leaves the editor (no keyboard trap)
      return
    }
    if (e.key !== "Tab" || tabMovesFocus.current || e.altKey || e.ctrlKey || e.metaKey) {
      tabMovesFocus.current = false
      return
    }
    e.preventDefault()
    const { selectionStart: start, selectionEnd: end, value } = el
    if (e.shiftKey) {
      const lineStart = value.lastIndexOf("\n", start - 1) + 1
      const spaces = value.slice(lineStart, lineStart + INDENT.length).match(/^ */)?.[0].length ?? 0
      if (!spaces) return
      el.setSelectionRange(lineStart, lineStart + spaces)
      if (!document.execCommand("delete")) el.setRangeText("", lineStart, lineStart + spaces, "end")
      el.setSelectionRange(Math.max(lineStart, start - spaces), Math.max(lineStart, end - spaces))
    } else if (!document.execCommand("insertText", false, INDENT)) {
      el.setRangeText(INDENT, start, end, "end") // execCommand keeps undo; this is the fallback
    }
    setCode(el.value)
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col gap-3" aria-label="Code editor panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex items-center gap-2 text-sm text-sub">
          Language
          <select
            value={language}
            onChange={(e) => {
              const next = e.target.value as Language
              setLanguage(next)
              write(LANG_KEY, next)
            }}
            className="min-h-9 rounded-lg border border-input-border bg-input-bg px-2 text-sm text-text hover:border-sub focus:border-accent focus:outline-none"
          >
            <option value="python">Python 3</option>
            <option value="cpp">C++17</option>
          </select>
        </label>
        <span className="hidden text-xs text-sub pointer-fine:inline">
          Tab indents · Esc, Tab leaves · Ctrl+Enter submits
        </span>
      </div>

      <textarea
        ref={textareaRef}
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={!canEdit}
        placeholder={language === "python" ? "# read input(), print the answer" : "// read stdin, print the answer"}
        spellCheck={false}
        autoCapitalize="off"
        autoCorrect="off"
        autoComplete="off"
        wrap="off"
        className="min-h-72 flex-1 resize-y rounded-lg border border-input-border bg-bg p-3 font-mono text-sm leading-6 text-text [tab-size:4] placeholder:text-sub focus:border-accent focus:outline-none disabled:opacity-60"
        aria-label="Code editor"
      />

      <VerdictPanel
        status={submitStatus}
        isSpectator={isSpectator}
        idleText={canEdit ? "No submission yet." : phase === "lobby" ? "The editor opens when the battle starts." : "Editing is closed."}
      />

      <div className="flex flex-col gap-1">
        <button type="submit" disabled={!canSubmit} className={btn.primary} aria-label="Submit code">
          <Icon name="play" />
          {running ? "Running…" : "Submit"}
        </button>
        {canEdit && disabledReason && <p className="text-center text-xs text-sub">{disabledReason}</p>}
      </div>
    </form>
  )
}
