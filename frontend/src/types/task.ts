export type TaskInfo = {
  id: number
  name: string
  description: string
  time_limit: { seconds: number; nanos: number } | null
  memory_limit_bytes: number | null
  public_tests: {
    input: string[]
    output: string[]
  }
}

export type Difficulty = "easy" | "medium" | "hard" | "unknown"

/** One catalog row (GET /api/tasks/): no tests, an excerpt instead of the statement. */
export type TaskListItem = {
  id: number
  name: string
  difficulty_label: Difficulty
  cf_rating: number | null
  cf_tags: string[]
  source_label: string | null
  source_slug: string | null
  time_limit_ms: number | null
  memory_limit_mb: number | null
  public_tests_count: number
  excerpt: string
}

export type Facet = { value: string; count: number; label?: string }

export type TaskFacets = {
  total: number
  difficulties: Facet[]
  sources: Facet[]
  tags: Facet[]
  rating: { min: number | null; max: number | null }
}
