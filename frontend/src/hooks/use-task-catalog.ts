import { useCallback, useEffect, useRef, useState } from "react"
import type { ApiResult } from "../lib/api"
import { fetchFacets, fetchTaskPage } from "../lib/tasks"
import type { ApiErrorState } from "../types/battle"
import type { TaskFacets, TaskListItem } from "../types/task"

export const CATALOG_PAGE = 30

type CatalogState = {
  key: string // the query these rows belong to
  items: TaskListItem[]
  count: number | null
  error: ApiErrorState | null // first page failed
  moreError: ApiErrorState | null // a later page failed
  loadingMore: boolean
}

const LOADING = "\u0000"
const empty: CatalogState = { key: LOADING, items: [], count: null, error: null, moreError: null, loadingMore: false }

/** The catalog rows for `query` (filters + ordering), loaded page by page as the list scrolls. */
export const useTaskCatalog = (query: string, onFirstPage?: (items: TaskListItem[]) => void) => {
  const [state, setState] = useState<CatalogState>(empty)
  const [attempt, setAttempt] = useState(0)
  const inFlight = useRef<string | null>(null)
  const firstPageRef = useRef(onFirstPage)

  useEffect(() => {
    firstPageRef.current = onFirstPage
  }, [onFirstPage])

  useEffect(() => {
    let cancelled = false
    fetchTaskPage(new URLSearchParams(query), CATALOG_PAGE, 0).then((r) => {
      if (cancelled) return
      if (r.ok) firstPageRef.current?.(r.data.results)
      setState(
        r.ok
          ? { ...empty, key: query, items: r.data.results, count: r.data.count }
          : { ...empty, key: query, error: r.error },
      )
    })
    return () => {
      cancelled = true
    }
  }, [query, attempt])

  const current = state.key === query ? state : null // null: the first page is loading
  const hasMore = !!current && !current.error && current.count !== null && current.items.length < current.count

  const loadMore = useCallback(() => {
    if (!current || !hasMore || current.loadingMore || inFlight.current === query) return
    inFlight.current = query
    const offset = current.items.length
    setState((s) => ({ ...s, loadingMore: true, moreError: null }))
    fetchTaskPage(new URLSearchParams(query), CATALOG_PAGE, offset).then((r) => {
      inFlight.current = null
      setState((s) => {
        if (s.key !== query) return s
        if (!r.ok) return { ...s, loadingMore: false, moreError: r.error }
        const seen = new Set(s.items.map((t) => t.id))
        const fresh = r.data.results.filter((t) => !seen.has(t.id))
        return { ...s, loadingMore: false, count: r.data.count, items: [...s.items, ...fresh] }
      })
    })
  }, [current, hasMore, query])

  const retry = useCallback(() => {
    setState(empty)
    setAttempt((n) => n + 1)
  }, [])

  return { current, hasMore, loadMore, retry }
}

// Facets change only with an import: one request per page load, shared by every catalog.
let facetsPromise: Promise<ApiResult<TaskFacets>> | null = null

export const useFacets = () => {
  const [facets, setFacets] = useState<TaskFacets | null>(null)
  useEffect(() => {
    let cancelled = false
    facetsPromise ??= fetchFacets()
    facetsPromise.then((r) => {
      if (!r.ok) facetsPromise = null // try again next time
      else if (!cancelled) setFacets(r.data)
    })
    return () => {
      cancelled = true
    }
  }, [])
  return facets
}
