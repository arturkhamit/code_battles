import { useCallback, useMemo } from "react"
import { useSearchParams } from "react-router-dom"
import { FILTER_KEYS, filterQuery } from "../lib/tasks"

/** Catalog filters and the chosen task, kept in the URL. */
export const useCatalogParams = () => {
  const [params, setParams] = useSearchParams()

  const update = useCallback(
    (changes: Record<string, string | null>, push = false) =>
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(changes)) {
            if (v) next.set(k, v)
            else next.delete(k)
          }
          return next
        },
        { replace: !push },
      ),
    [setParams],
  )

  const resetFilters = useCallback(
    () => update(Object.fromEntries(FILTER_KEYS.map((k) => [k, null]))),
    [update],
  )

  const query = useMemo(() => filterQuery(params).toString(), [params])
  const taskParam = Number(params.get("task"))
  const taskId = Number.isInteger(taskParam) && taskParam > 0 ? taskParam : null

  return { params, update, resetFilters, query, taskId }
}
