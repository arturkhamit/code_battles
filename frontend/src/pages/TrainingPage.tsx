import { useCallback, useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { CodePanel } from "../components/CodePanel"
import { TaskCatalog } from "../components/catalog/TaskCatalog"
import { FloatingCard } from "../components/layout/FloatingCard"
import { TaskPanel } from "../components/TaskPanel"
import { Icon } from "../components/ui/Icon"
import { useCatalogParams } from "../hooks/use-catalog-params"
import { usePageTitle } from "../hooks/use-page-title"
import { fetchTaskInfo, fetchTaskItem } from "../lib/tasks"
import { authFetch } from "../lib/token-store"
import { btn } from "../lib/ui"
import { verdictStatus } from "../lib/verdict"
import { CONFIG } from "../config"
import type { Language, SubmitStatus } from "../types/battle"
import type { TaskInfo, TaskListItem } from "../types/task"
import type { ExecutionResult } from "../types/ws"

type Loaded<T> = { id: number; data: T | null; error: string | null }

/** The statement and catalog row of one task, refetched when the id changes. */
const useTask = (id: number | null, rows: TaskListItem[]) => {
  const [info, setInfo] = useState<Loaded<TaskInfo> | null>(null)
  const [row, setRow] = useState<TaskListItem | null>(null)
  useEffect(() => {
    if (id === null) return
    let cancelled = false
    fetchTaskInfo(id).then((r) => {
      if (!cancelled) setInfo({ id, data: r.ok ? r.data : null, error: r.ok ? null : r.error.message })
    })
    return () => {
      cancelled = true
    }
  }, [id])
  const known = rows.find((t) => t.id === id) ?? null
  useEffect(() => {
    if (id === null || known) return
    let cancelled = false
    fetchTaskItem(id).then((r) => !cancelled && r.ok && setRow(r.data)) // a shared link: not in the list yet
    return () => {
      cancelled = true
    }
  }, [id, known])
  const current = info?.id === id ? info : null
  return { task: current?.data ?? null, error: current?.error ?? null, item: known ?? (row?.id === id ? row : null) }
}

export const TrainingPage = () => {
  const navigate = useNavigate()
  const { update, taskId } = useCatalogParams()
  const [rows, setRows] = useState<TaskListItem[]>([])
  // the first task stands in on wide screens until one is chosen; phones show the list instead
  const selectedId = taskId ?? rows[0]?.id ?? null
  const { task, error, item } = useTask(selectedId, rows)
  const [submit, setSubmit] = useState<{ id: number | null; status: SubmitStatus }>({ id: null, status: { kind: "none" } })
  const [cooldown, setCooldown] = useState(0)
  const editorRef = useRef<HTMLTextAreaElement>(null)
  usePageTitle(task && taskId ? task.name : "Training")

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const handleSelect = useCallback(
    (id: number, row: TaskListItem) => {
      setRows((r) => (r.some((t) => t.id === id) ? r : [row, ...r]))
      update({ task: String(id) }, true)
      if (window.matchMedia("(max-width: 1023px)").matches) window.scrollTo({ top: 0 })
    },
    [update],
  )

  const handleSubmit = useCallback(
    async (code: string, language: Language) => {
      if (selectedId === null) return
      setSubmit({ id: selectedId, status: { kind: "running" } })
      const result = await authFetch<ExecutionResult>(`${CONFIG.FASTAPI_URL}/api/tasks/${selectedId}/submit`, {
        method: "POST",
        body: JSON.stringify({ language, code }),
      })
      if (!result.ok) {
        if (result.error.status === 429) setCooldown(result.error.retryAfter ?? 1)
        setSubmit({ id: selectedId, status: { kind: "error", message: result.error.message } })
        return
      }
      setSubmit({ id: selectedId, status: verdictStatus(result.data) })
    },
    [selectedId],
  )

  const status: SubmitStatus = submit.id === selectedId ? submit.status : { kind: "none" }
  const shownStatus: SubmitStatus =
    cooldown > 0 && status.kind === "error" ? { kind: "error", message: `${status.message}\nToo frequent. Retry in ${cooldown} s.` } : status
  const solve = () => {
    editorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" })
    editorRef.current?.focus({ preventScroll: true })
  }

  return (
    <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[minmax(20rem,24rem)_1fr] xl:h-[calc(100dvh-7rem)] xl:min-h-[36rem] xl:flex-none">
      <h1 className="sr-only">Training</h1>
      <FloatingCard
        title="Problems"
        className={`min-h-[70dvh] lg:sticky lg:top-4 lg:h-[calc(100dvh-2rem)] lg:min-h-0 xl:static xl:h-auto ${taskId ? "max-lg:hidden" : ""}`}
      >
        <TaskCatalog selectedId={selectedId} onSelect={handleSelect} onFirstPage={setRows} />
      </FloatingCard>

      <div className={`grid min-h-0 min-w-0 grid-cols-1 gap-4 xl:grid-cols-[1fr_1.15fr] ${taskId ? "" : "max-lg:hidden"}`}>
        <FloatingCard aria-label="Problem statement" className="min-h-0">
          <button type="button" onClick={() => update({ task: null })} className={`${btn.ghost} -ml-2 mb-2 self-start px-2 lg:hidden`}>
            <Icon name="back" />
            All problems
          </button>
          {selectedId === null && !error ? (
            <p className="text-sm text-sub">Choose a problem from the list.</p>
          ) : (
            <TaskPanel
              task={task}
              item={item}
              phase="active"
              error={error}
              actions={
                task && (
                  <>
                    <button type="button" onClick={solve} className={`${btn.primary} xl:hidden`}>
                      Solve
                    </button>
                    <button type="button" onClick={() => navigate(`/unranked?task=${task.id}`)} className={btn.secondary}>
                      <Icon name="lightning" />
                      Pick for battle
                    </button>
                  </>
                )
              }
            />
          )}
        </FloatingCard>

        <FloatingCard title="Your solution" className="min-h-[28rem] xl:min-h-0">
          <CodePanel
            key={selectedId ?? "none"}
            phase="active"
            isSpectator={false}
            submitStatus={shownStatus}
            onSubmit={handleSubmit}
            disabled={selectedId === null || cooldown > 0}
            disabledReason={cooldown > 0 ? `You can submit again in ${cooldown} s.` : undefined}
            draftKey={selectedId ? `cb_draft_${selectedId}` : undefined}
            textareaRef={editorRef}
          />
        </FloatingCard>
      </div>
    </div>
  )
}
