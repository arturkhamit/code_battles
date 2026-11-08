import { CONFIG } from "../config"
import type { Page } from "../types/battle"
import type { Difficulty, TaskFacets, TaskInfo, TaskListItem } from "../types/task"
import { authFetch } from "./token-store"

// The catalog filters live in the URL under the API's own names, so a link reproduces the view
// and the query string goes to /api/tasks/ as is (FastAPI whitelists every value).
export const FILTER_KEYS = ["search", "difficulty", "tags", "source", "rating_min", "rating_max", "ordering"] as const
export type FilterKey = (typeof FILTER_KEYS)[number]

export const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard", "unknown"]

export const ORDERINGS: { value: string; label: string }[] = [
  { value: "", label: "Number" },
  { value: "difficulty", label: "Easiest first" },
  { value: "-difficulty", label: "Hardest first" },
  { value: "cf_rating", label: "Rating, low to high" },
  { value: "-cf_rating", label: "Rating, high to low" },
  { value: "name", label: "Name, A to Z" },
  { value: "time_limit", label: "Shortest time limit" },
  { value: "-memory_limit", label: "Most memory" },
  { value: "-tests", label: "Most examples" },
]

export const filterQuery = (params: URLSearchParams): URLSearchParams => {
  const query = new URLSearchParams()
  for (const key of FILTER_KEYS) {
    const value = params.get(key)?.trim()
    if (value) query.set(key, value)
  }
  return query
}

/** Filters that narrow the list (ordering only sorts it). */
export const activeFilterCount = (params: URLSearchParams) =>
  FILTER_KEYS.filter((k) => k !== "ordering" && params.get(k)?.trim()).length

export const csv = (params: URLSearchParams, key: FilterKey) =>
  (params.get(key) ?? "").split(",").filter(Boolean)

export const fetchTaskPage = (query: URLSearchParams, limit: number, offset: number) => {
  const q = new URLSearchParams(query)
  q.set("limit", String(limit))
  q.set("offset", String(offset))
  return authFetch<Page<TaskListItem>>(`${CONFIG.FASTAPI_URL}/api/tasks/?${q}`)
}

export const fetchFacets = () => authFetch<TaskFacets>(`${CONFIG.FASTAPI_URL}/api/tasks/facets/`)

export const fetchRandomTask = (query: URLSearchParams) => {
  const q = new URLSearchParams(query)
  q.delete("ordering")
  return authFetch<TaskListItem>(`${CONFIG.FASTAPI_URL}/api/tasks/random?${q}`)
}

export const fetchTaskInfo = (id: number) =>
  authFetch<TaskInfo>(`${CONFIG.FASTAPI_URL}/api/tasks/${id}/info`)

/** The catalog row of one task, for a card when only its id is known (a link, a typed id). */
export const fetchTaskItem = async (id: number) => {
  const result = await fetchTaskPage(new URLSearchParams({ search: String(id) }), 100, 0)
  if (!result.ok) return result
  const item = result.data.results.find((t) => t.id === id)
  return item
    ? ({ ok: true, data: item } as const)
    : ({ ok: false, error: { message: `Task ${id} does not exist.`, status: 404, isHtml: false } } as const)
}

export const formatTimeLimit = (ms: number | null | undefined) => {
  if (!ms) return null
  return ms % 1000 === 0 ? `${ms / 1000} s` : `${(ms / 1000).toFixed(1)} s`
}

export const formatMemory = (mb: number | null | undefined) => {
  if (!mb) return null
  return mb >= 1024 && mb % 1024 === 0 ? `${mb / 1024} GB` : `${mb} MB`
}

export const timeLimitMs = (t: TaskInfo["time_limit"]) =>
  t ? t.seconds * 1000 + Math.round((t.nanos ?? 0) / 1e6) : null

export const memoryMb = (bytes: number | null) => (bytes ? Math.floor(bytes / 2 ** 20) : null)
