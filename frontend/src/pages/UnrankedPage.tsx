import { useEffect, useState, type FormEvent } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { DebouncedInput } from "../components/catalog/DebouncedInput"
import { TaskPickerDialog } from "../components/catalog/TaskPickerDialog"
import { TaskCard } from "../components/catalog/TaskCard"
import { ErrorBanner } from "../components/ErrorBanner"
import { FloatingCard } from "../components/layout/FloatingCard"
import { OpenLobbies } from "../components/OpenLobbies"
import { Field } from "../components/ui/Field"
import { Icon } from "../components/ui/Icon"
import { useCatalogParams } from "../hooks/use-catalog-params"
import { usePageTitle } from "../hooks/use-page-title"
import { createBattle, rememberBattle } from "../lib/battles"
import { activeFilterCount, csv, fetchRandomTask, fetchTaskItem, filterQuery } from "../lib/tasks"
import { btn, describedBy, inputClass } from "../lib/ui"
import type { ApiErrorState, BattleType } from "../types/battle"
import type { TaskListItem } from "../types/task"

const DURATIONS = [5, 10, 15, 20, 30, 45, 60, 90, 120]
const SIZES = [2, 3, 4, 5, 6, 7, 8, 9, 10]

/** "/join/CODE", "/battle/12?invite=CODE", "12" or a bare code -> where to go */
const joinTarget = (raw: string): string | null => {
  const text = raw.trim()
  if (!text) return null
  const battle = text.match(/\/battle\/(\d+)(\?.*)?$/)
  if (battle) return `/battle/${battle[1]}${battle[2] ?? ""}`
  const join = text.match(/\/join\/([^/?#\s]+)/)
  if (join) return `/join/${join[1]}`
  if (/^\d+$/.test(text)) return `/battle/${text}`
  return `/join/${encodeURIComponent(text)}`
}

const filterSummary = (params: URLSearchParams) => {
  const parts = [
    csv(params, "difficulty").join(" or "),
    csv(params, "tags").join(" + "),
    params.get("rating_min") || params.get("rating_max")
      ? `rating ${params.get("rating_min") ?? "…"}–${params.get("rating_max") ?? "…"}`
      : "",
    params.get("search") ? `“${params.get("search")}”` : "",
    csv(params, "source").join(", "),
  ].filter(Boolean)
  return parts.length ? parts.join(" · ") : "any task"
}

const ChosenTask = ({ id, onBrowse }: { id: number | null; onBrowse: () => void }) => {
  const [loaded, setLoaded] = useState<{ id: number; item: TaskListItem | null; error: string | null } | null>(null)
  useEffect(() => {
    if (id === null) return
    let cancelled = false
    fetchTaskItem(id).then((r) => {
      if (!cancelled) setLoaded({ id, item: r.ok ? r.data : null, error: r.ok ? null : r.error.message })
    })
    return () => {
      cancelled = true
    }
  }, [id])

  if (id === null) {
    return (
      <button type="button" onClick={onBrowse} className="rounded-lg border border-dashed border-input-border p-4 text-left text-sm text-sub hover:border-sub hover:text-text">
        No task chosen yet. Browse the catalog or roll a random one.
      </button>
    )
  }
  const current = loaded?.id === id ? loaded : null
  if (!current) return <div className="h-24 animate-pulse rounded-lg bg-bg" aria-label="Loading the task" />
  if (!current.item) return <p className="rounded-lg border border-error/40 bg-error/10 p-3 text-sm text-error">{current.error}</p>
  return (
    <div className="rounded-lg border border-input-border bg-bg/60" data-testid="chosen-task">
      <TaskCard task={current.item} selected={false} onSelect={onBrowse} />
    </div>
  )
}

export const UnrankedPage = () => {
  usePageTitle("Unranked battles")
  const navigate = useNavigate()
  const location = useLocation()
  const { params, update, taskId: urlTask } = useCatalogParams()
  const stateTask = (location.state as { taskId?: number } | null)?.taskId ?? null
  const taskId = urlTask ?? stateTask

  const [battleType, setBattleType] = useState<BattleType>("1v1")
  const [duration, setDuration] = useState("15")
  const [maxParticipants, setMaxParticipants] = useState("10")
  const [isPrivate, setIsPrivate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<ApiErrorState | null>(null)
  const [taskError, setTaskError] = useState<string[] | undefined>()
  const [picking, setPicking] = useState(false)
  const [rolling, setRolling] = useState(false)
  const [joinInput, setJoinInput] = useState("")
  const filtered = activeFilterCount(params) > 0

  const chooseTask = (id: number | null) => {
    setTaskError(undefined)
    update({ task: id ? String(id) : null })
  }

  const handleRandom = async () => {
    setRolling(true)
    const r = await fetchRandomTask(filterQuery(params))
    setRolling(false)
    if (r.ok) chooseTask(r.data.id)
    else setTaskError([r.error.status === 404 ? "No task matches the catalog filters. Reset them in Browse." : r.error.message])
  }

  const handleCreate = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (creating) return
    // the typed id may still be in the debounce: read the field itself
    const task = Number(new FormData(e.currentTarget).get("task") ?? taskId)
    if (!Number.isInteger(task) || task < 1) {
      setTaskError(["Enter a task number or pick one from the catalog."])
      return
    }
    setCreating(true)
    setError(null)
    const result = await createBattle({
      task,
      type: battleType,
      duration: Number(duration),
      max_participants: battleType === "group" ? Number(maxParticipants) : undefined,
      is_private: isPrivate,
      ranked: false,
    })
    setCreating(false)
    if (!result.ok) {
      setError(result.error)
      return
    }
    const b = result.data
    rememberBattle(b.id, { invite: b.invite_code, task: b.task, type: b.type })
    navigate(`/battle/${b.id}`)
  }

  const handleJoin = (e: FormEvent) => {
    e.preventDefault()
    const target = joinTarget(joinInput)
    if (target) navigate(target)
  }

  const fieldErrors = error?.fieldErrors ?? {}
  const taskErrors = taskError ?? fieldErrors.task
  const otherErrors = error && Object.keys(fieldErrors).some((k) => !["task", "duration", "max_participants"].includes(k))

  return (
    <div className="grid flex-1 grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_minmax(20rem,24rem)]">
      <h1 className="sr-only">Unranked battles</h1>
      <FloatingCard title="Create a battle">
        <form onSubmit={handleCreate} className="flex flex-col gap-5" noValidate>
          <section className="flex flex-col gap-2" aria-labelledby="task-heading">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 id="task-heading" className="text-sm font-medium text-text">Task</h3>
              <div className="flex gap-2">
                <button type="button" onClick={() => setPicking(true)} className={btn.secondary}>
                  <Icon name="book" />
                  Browse
                </button>
                <button type="button" onClick={handleRandom} disabled={rolling} className={btn.secondary} aria-describedby="random-scope">
                  <Icon name="shuffle" />
                  {rolling ? "Rolling…" : "Random task"}
                </button>
              </div>
            </div>
            <ChosenTask id={taskId} onBrowse={() => setPicking(true)} />
            <p id="random-scope" className="text-xs text-sub">
              Random picks from {filterSummary(params)}
              {filtered && (
                <>
                  {" "}
                  (the catalog filters).{" "}
                  <button type="button" onClick={() => setPicking(true)} className="text-accent hover:underline">Change</button>
                </>
              )}
            </p>
            <Field id="task" label="Task ID" errors={taskErrors} help="Or type the task number.">
              <DebouncedInput
                name="task"
                type="number"
                inputMode="numeric"
                min={1}
                value={taskId ? String(taskId) : ""}
                onCommit={(v) => chooseTask(Number(v) > 0 ? Number(v) : null)}
                className={`${inputClass} max-w-40`}
                {...describedBy("task", true, taskErrors)}
              />
            </Field>
          </section>

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-medium text-text">Battle type</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {(
                [
                  ["1v1", "1v1 duel", "Exactly two players. The first to pass all tests wins."],
                  ["group", "Group", "Two or more players race on the same task."],
                ] as const
              ).map(([value, title, text]) => (
                <label key={value} className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition ${battleType === value ? "border-accent bg-accent/10" : "border-input-border hover:border-sub"}`}>
                  <input type="radio" name="type" value={value} checked={battleType === value} onChange={() => setBattleType(value)} className="mt-1 accent-[var(--color-accent)]" />
                  <span>
                    <span className="block text-sm font-medium text-text">{title}</span>
                    <span className="block text-xs text-sub">{text}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="duration" label="Duration" errors={fieldErrors.duration}>
              <select value={duration} onChange={(e) => setDuration(e.target.value)} className={inputClass} {...describedBy("duration", false, fieldErrors.duration)}>
                {DURATIONS.map((m) => (
                  <option key={m} value={m}>{m} minutes</option>
                ))}
              </select>
            </Field>
            {battleType === "group" && (
              <Field id="max_participants" label="Players at most" errors={fieldErrors.max_participants}>
                <select value={maxParticipants} onChange={(e) => setMaxParticipants(e.target.value)} className={inputClass} {...describedBy("max_participants", false, fieldErrors.max_participants)}>
                  {SIZES.map((n) => (
                    <option key={n} value={n}>{n} players</option>
                  ))}
                </select>
              </Field>
            )}
          </div>

          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-input-border p-3 hover:border-sub">
            <input type="checkbox" checked={isPrivate} onChange={(e) => setIsPrivate(e.target.checked)} className="mt-1 accent-[var(--color-accent)]" aria-describedby="private-help" />
            <span>
              <span className="flex items-center gap-1.5 text-sm font-medium text-text">
                <Icon name="lock" className="h-3.5 w-3.5" />
                Private
              </span>
              <span id="private-help" className="block text-xs text-sub">
                Not listed in open lobbies. Only people with the invite link can join.
              </span>
            </span>
          </label>

          {error && (otherErrors || !Object.keys(fieldErrors).length) && <ErrorBanner error={error} onDismiss={() => setError(null)} />}

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-sub">Unranked: your rating does not change. You start the battle when everyone is in.</p>
            <button type="submit" disabled={creating} className={btn.primary} aria-label="Create battle">
              <Icon name="play" />
              {creating ? "Creating…" : "Create battle"}
            </button>
          </div>
        </form>
      </FloatingCard>

      <div className="flex flex-col gap-4">
        <FloatingCard title="Join a battle">
          <form onSubmit={handleJoin} className="flex gap-2">
            <input
              type="text"
              value={joinInput}
              onChange={(e) => setJoinInput(e.target.value)}
              placeholder="Battle ID, invite code or link"
              className={inputClass}
              aria-label="Battle ID, invite code or link"
              autoCapitalize="off"
              autoCorrect="off"
            />
            <button type="submit" disabled={!joinInput.trim()} className={btn.secondary}>
              Join
            </button>
          </form>
        </FloatingCard>
        <OpenLobbies />
      </div>

      <TaskPickerDialog
        open={picking}
        initialId={taskId}
        onClose={() => setPicking(false)}
        onPick={(id) => {
          chooseTask(id)
          setPicking(false)
        }}
      />
    </div>
  )
}
