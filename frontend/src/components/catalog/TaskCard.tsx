import { formatMemory, formatTimeLimit } from "../../lib/tasks"
import type { TaskListItem } from "../../types/task"
import { DifficultyBadge } from "../ui/DifficultyBadge"

const MAX_TAGS = 3

/** A catalog row. Its text starts with the task number (e2e and screen readers read it first). */
export const TaskCard = ({ task, selected, onSelect }: { task: TaskListItem; selected: boolean; onSelect: (id: number, task: TaskListItem) => void }) => {
  const limits = [formatTimeLimit(task.time_limit_ms), formatMemory(task.memory_limit_mb)].filter(Boolean).join(" · ")
  const extraTags = task.cf_tags.length - MAX_TAGS
  return (
    <button
      type="button"
      onClick={() => onSelect(task.id, task)}
      aria-current={selected ? "true" : undefined}
      className={`flex w-full flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-left transition ${
        selected ? "border-accent/60 bg-bg" : "border-transparent hover:border-input-border hover:bg-bg/60"
      }`}
    >
      <span className="flex w-full items-start gap-2">
        <span className="num pt-px font-mono text-xs text-sub">{task.id}</span>
        <span className="line-clamp-2 min-w-0 flex-1 text-sm font-medium [overflow-wrap:anywhere] text-text">{task.name}</span>
      </span>
      {task.excerpt && <span className="line-clamp-2 text-xs leading-relaxed text-sub">{task.excerpt}</span>}
      <span className="flex w-full flex-wrap items-center gap-1.5 text-xs text-sub">
          <span className="mr-1">
            <DifficultyBadge label={task.difficulty_label} rating={task.cf_rating} />
          </span>
          {task.cf_tags.slice(0, MAX_TAGS).map((tag) => (
            <span key={tag} className="max-w-40 truncate rounded bg-input-bg px-1.5 py-0.5">
              {tag}
            </span>
          ))}
          {extraTags > 0 && <span>+{extraTags}</span>}
          {limits && <span className="num ml-auto whitespace-nowrap">{limits}</span>}
      </span>
    </button>
  )
}

export const TaskCardSkeleton = () => (
  <div className="flex flex-col gap-2 px-3 py-3" aria-hidden="true">
    <div className="h-4 w-3/4 animate-pulse rounded bg-input-bg" />
    <div className="h-3 w-full animate-pulse rounded bg-input-bg" />
    <div className="h-3 w-1/2 animate-pulse rounded bg-input-bg" />
  </div>
)
