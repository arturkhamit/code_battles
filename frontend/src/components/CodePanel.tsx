import { useState, useCallback, type FormEvent } from "react"
import type { BattlePhase, Language, SubmitStatus } from "../types/battle"

type CodePanelProps = {
  phase: BattlePhase
  submitStatus: SubmitStatus
  onSubmit: (code: string, language: Language) => void
}

const statusBannerClass = (status: SubmitStatus): string => {
  const base =
    "rounded border p-2.5 text-center text-sm font-bold"
  switch (status.kind) {
    case "none":
      return `${base} border-ctp-surface1 bg-ctp-mantle text-ctp-text`
    case "running":
      return `${base} border-ctp-yellow bg-ctp-yellow/10 text-ctp-yellow`
    case "accepted":
      return `${base} border-ctp-green bg-ctp-green/10 text-ctp-green`
    case "wrong":
    case "error":
      return `${base} border-ctp-red bg-ctp-red/10 text-ctp-red`
  }
}

const statusText = (status: SubmitStatus): string => {
  switch (status.kind) {
    case "none":
      return "Status: no submissions"
    case "running":
      return "Code is running..."
    case "accepted":
      return status.message
    case "wrong":
      return `WRONG ANSWER: ${status.message}`
    case "error":
      return status.message
  }
}

export const CodePanel = ({ phase, submitStatus, onSubmit }: CodePanelProps) => {
  const [code, setCode] = useState("")
  const [language, setLanguage] = useState<Language>("python")

  const canEdit = phase === "active"
  const canSubmit = phase === "active" && submitStatus.kind !== "running"

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault()
      if (!canSubmit || !code.trim()) return
      onSubmit(code, language)
    },
    [canSubmit, code, language, onSubmit],
  )

  const handleLoadBadCode = useCallback(() => {
    setCode("print('no')")
  }, [])

  const handleLoadGoodCode = useCallback(() => {
    setCode("print('yes')")
  }, [])

  return (
    <section
      className="flex flex-[1.2] flex-col overflow-y-auto rounded-xl bg-ctp-surface0 p-4 shadow-lg"
      aria-label="Code editor panel"
    >
      <div className={statusBannerClass(submitStatus)} role="status">
        {statusText(submitStatus)}
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex flex-1 flex-col gap-3">
        <div className="flex items-center justify-between">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as Language)}
            className="rounded border border-ctp-surface1 bg-ctp-crust px-2 py-1.5 text-sm text-ctp-text outline-none focus:border-ctp-blue"
            aria-label="Programming language"
          >
            <option value="python">Python 3</option>
            <option value="cpp">C++</option>
          </select>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleLoadBadCode}
              className="rounded bg-ctp-surface1 px-2 py-1 text-xs text-ctp-text transition hover:bg-ctp-surface2"
              tabIndex={0}
            >
              Bad code
            </button>
            <button
              type="button"
              onClick={handleLoadGoodCode}
              className="rounded bg-ctp-surface1 px-2 py-1 text-xs text-ctp-text transition hover:bg-ctp-surface2"
              tabIndex={0}
            >
              Good code
            </button>
          </div>
        </div>

        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          disabled={!canEdit}
          placeholder="# Your code..."
          className="flex-1 resize-none rounded border border-ctp-surface1 bg-ctp-crust p-3 font-mono text-sm text-ctp-green outline-none transition focus:border-ctp-blue disabled:opacity-50"
          aria-label="Code editor"
        />

        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded bg-ctp-green py-2.5 text-base font-bold text-ctp-crust transition hover:bg-ctp-teal disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
          tabIndex={0}
          aria-label="Submit code"
        >
          Send code
        </button>
      </form>
    </section>
  )
}
