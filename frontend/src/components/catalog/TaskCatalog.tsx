import { useEffect, useRef } from "react"
import { useCatalogParams } from "../../hooks/use-catalog-params"
import { useFacets, useTaskCatalog } from "../../hooks/use-task-catalog"
import { activeFilterCount } from "../../lib/tasks"
import { btn } from "../../lib/ui"
import type { TaskListItem } from "../../types/task"
import { CatalogFilters, SortSelect } from "./CatalogFilters"
import { TaskCard, TaskCardSkeleton } from "./TaskCard"

type Props = {
  selectedId: number | null
  onSelect: (id: number, task: TaskListItem) => void
  onFirstPage?: (items: TaskListItem[]) => void
}

const fmt = new Intl.NumberFormat("en-US")

/** Search, filters, sort and an endlessly loading list of tasks; the filters live in the URL. */
export const TaskCatalog = ({ selectedId, onSelect, onFirstPage }: Props) => {
  const { params, update, resetFilters, query } = useCatalogParams()
  const facets = useFacets()
  const { current, hasMore, loadMore, retry } = useTaskCatalog(query, onFirstPage)
  const sentinel = useRef<HTMLLIElement>(null)
  const filtered = activeFilterCount(params) > 0

  useEffect(() => {
    const el = sentinel.current
    if (!el || !hasMore) return
    // root: the viewport; it still sees through the list's own scroll box
    const observer = new IntersectionObserver((entries) => entries[0]?.isIntersecting && loadMore(), { rootMargin: "400px 0px" })
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, loadMore])

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <CatalogFilters params={params} update={update} facets={facets} />

      <div className="flex min-h-8 flex-wrap items-center justify-between gap-2 text-xs text-sub">
        <span aria-live="polite" className="num">
          {current?.count != null
            ? `${fmt.format(current.items.length)} of ${fmt.format(current.count)} problems`
            : current?.error
              ? "Problems could not load"
              : "Loading problems…"}
        </span>
        <span className="flex items-center gap-2">
          {filtered && (
            <button type="button" onClick={resetFilters} className="font-medium text-accent hover:underline">
              Reset filters
            </button>
          )}
          <SortSelect value={params.get("ordering") ?? ""} onChange={(v) => update({ ordering: v || null })} />
        </span>
      </div>

      <ul data-testid="task-list" aria-label="Problems" aria-busy={!current} className="-mx-2 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overscroll-contain px-2 pb-2">
        {!current && [0, 1, 2, 3, 4, 5].map((i) => <li key={i}><TaskCardSkeleton /></li>)}

        {current?.error && (
          <li className="flex flex-col items-start gap-3 rounded-lg border border-error/40 bg-error/10 p-4 text-sm text-error" role="alert">
            <span>Problems could not load: {current.error.message}</span>
            <span className="flex gap-2">
              <button type="button" onClick={retry} className={btn.small + " bg-error/20 text-text"}>Try again</button>
              {filtered && <button type="button" onClick={resetFilters} className={btn.small + " text-text"}>Reset filters</button>}
            </span>
          </li>
        )}

        {current && !current.error && current.items.length === 0 && (
          <li className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-input-border p-4 text-sm">
            <span className="font-medium text-text">No problem matches these filters.</span>
            <span className="text-sub">Try fewer tags, another difficulty or a wider rating range.</span>
            {filtered && <button type="button" onClick={resetFilters} className={btn.secondary}>Reset filters</button>}
          </li>
        )}

        {current?.items.map((task) => (
          <li key={task.id}>
            <TaskCard task={task} selected={task.id === selectedId} onSelect={onSelect} />
          </li>
        ))}

        {current && hasMore && (
          <li ref={sentinel} className="flex flex-col items-center gap-2 py-2">
            {current.loadingMore && <TaskCardSkeleton />}
            {current.moreError && <span className="text-xs text-error">{current.moreError.message}</span>}
            {!current.loadingMore && (
              <button type="button" onClick={loadMore} className={btn.small + " border border-input-border text-sub hover:text-text"}>
                Load more
              </button>
            )}
          </li>
        )}
        {current && !hasMore && current.items.length > 0 && (
          <li className="py-3 text-center text-xs text-sub">End of the list.</li>
        )}
      </ul>
    </div>
  )
}
