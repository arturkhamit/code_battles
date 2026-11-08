import type { ReactNode } from "react"
import { stripSamples } from "../lib/statement"
import { formatMemory, formatTimeLimit, memoryMb, timeLimitMs } from "../lib/tasks"
import type { BattlePhase } from "../types/battle"
import type { TaskInfo, TaskListItem } from "../types/task"
import { DifficultyBadge } from "./ui/DifficultyBadge"
import { Icon } from "./ui/Icon"

type TaskPanelProps = {
  task: TaskInfo | null
  /** the catalog row, when known: difficulty, rating, tags */
  item?: TaskListItem | null
  phase: BattlePhase
  error?: string | null
  actions?: ReactNode
}

// code_contests statements are plain text with these headings on lines of their own
const HEADING = /^(input|output|examples?|notes?|constraints|explanation|interaction|scoring|subtasks?)\s*:?$/i

const Statement = ({ text }: { text: string }) => {
  const blocks = text.replace(/^\s*Problem (description|statement)\.?\s*/i, "").split(/\n\s*\n/)
  return (
    <div className="flex flex-col gap-3 text-sm leading-relaxed text-text/90">
      {blocks.map((block, i) => {
        const trimmed = block.trim()
        if (!trimmed) return null
        if (HEADING.test(trimmed)) {
          return (
            <h3 key={i} className="mt-2 text-sm font-semibold text-text">
              {trimmed.replace(/:$/, "")}
            </h3>
          )
        }
        return (
          <p key={i} className="break-words whitespace-pre-wrap">
            {trimmed}
          </p>
        )
      })}
    </div>
  )
}

const Skeleton = () => (
  <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading the task">
    <div className="h-6 w-2/3 animate-pulse rounded bg-input-bg" />
    <div className="h-4 w-1/3 animate-pulse rounded bg-input-bg" />
    {[0, 1, 2, 3, 4].map((i) => (
      <div key={i} className="h-4 animate-pulse rounded bg-input-bg" style={{ width: `${90 - i * 9}%` }} />
    ))}
  </div>
)

export const TaskPanel = ({ task, item, phase, error, actions }: TaskPanelProps) => {
  if (!task) {
    return (
      <div className="flex min-h-0 flex-1 flex-col" aria-label="Task panel">
        {error ? (
          <p className="text-sm text-error" role="alert">
            {error}
          </p>
        ) : phase === "closed" ? (
          <p className="text-sm text-sub">Not connected to the battle.</p>
        ) : phase === "connecting" ? (
          <p className="text-sm text-sub">Connecting to the battle…</p>
        ) : (
          <Skeleton />
        )}
      </div>
    )
  }

  const inputs = task.public_tests?.input ?? []
  const outputs = task.public_tests?.output ?? []
  const time = formatTimeLimit(timeLimitMs(task.time_limit))
  const memory = formatMemory(memoryMb(task.memory_limit_bytes))

  return (
    <article className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto" aria-label="Task panel">
      <header className="flex flex-col gap-2">
        <h2 className="text-lg leading-snug font-semibold break-words text-text">
          <span className="num mr-2 font-mono text-sub">{task.id}</span>
          {task.name}
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-sub">
          {item && <DifficultyBadge label={item.difficulty_label} rating={item.cf_rating} />}
          <span className="inline-flex items-center gap-1">
            <Icon name="clock" className="h-3.5 w-3.5" />
            {time ?? "No time limit"}
          </span>
          <span className="inline-flex items-center gap-1">
            <Icon name="chip" className="h-3.5 w-3.5" />
            {memory ?? "No memory limit"}
          </span>
          {item?.source_label && <span>{item.source_label}</span>}
        </div>
        {item && item.cf_tags.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Tags">
            {item.cf_tags.map((tag) => (
              <li key={tag} className="rounded-md bg-input-bg px-2 py-0.5 text-xs whitespace-nowrap text-sub">
                {tag}
              </li>
            ))}
          </ul>
        )}
        {actions && <div className="mt-1 flex flex-wrap gap-2">{actions}</div>}
      </header>

      <Statement text={stripSamples(task.description, inputs.length > 0)} />

      <section aria-label="Sample tests">
        <h3 className="mb-2 text-sm font-semibold text-text">Sample tests</h3>
        {inputs.length === 0 && <p className="text-xs text-sub">This task has no public examples.</p>}
        <div className="flex flex-col gap-3">
          {inputs.map((input, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-2">
              <div className="min-w-0 rounded-lg bg-bg p-3">
                <div className="text-xs font-medium text-sub">Input {inputs.length > 1 ? i + 1 : ""}</div>
                <pre className="mt-1 max-h-60 overflow-auto font-mono text-sm whitespace-pre text-text">{input}</pre>
              </div>
              {outputs[i] !== undefined && (
                <div className="min-w-0 rounded-lg bg-bg p-3">
                  <div className="text-xs font-medium text-sub">Expected output</div>
                  <pre className="mt-1 max-h-60 overflow-auto font-mono text-sm whitespace-pre text-main">{outputs[i]}</pre>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </article>
  )
}
