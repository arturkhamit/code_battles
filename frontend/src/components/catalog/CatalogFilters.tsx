import { useId, useState } from "react"
import { activeFilterCount, csv, DIFFICULTIES, ORDERINGS, type FilterKey } from "../../lib/tasks"
import { chipClass, difficultyDot, inputClass } from "../../lib/ui"
import type { TaskFacets } from "../../types/task"
import { Icon } from "../ui/Icon"
import { DebouncedInput } from "./DebouncedInput"

export type FilterUpdate = Partial<Record<FilterKey, string | null>>

type Props = {
  params: URLSearchParams
  update: (changes: FilterUpdate) => void
  facets: TaskFacets | null
}

const TAGS_SHOWN = 24

const rating = (v: string) => {
  const n = Number(v)
  return v.trim() && Number.isInteger(n) && n >= 0 && n <= 5000 ? String(n) : null
}

const toggle = (list: string[], value: string) =>
  (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]).join(",") || null

export const CatalogFilters = ({ params, update, facets }: Props) => {
  const uid = useId()
  const [open, setOpen] = useState(false)
  const [tagQuery, setTagQuery] = useState("")
  const difficulties = csv(params, "difficulty")
  const tags = csv(params, "tags")
  const sources = csv(params, "source")
  // the panel's own filters, so a closed panel still says it is narrowing the list
  const panelCount = activeFilterCount(params) - (params.get("search") ? 1 : 0) - (difficulties.length ? 1 : 0)
  const difficultyCount = (value: string) => facets?.difficulties.find((d) => d.value === value)?.count

  const needle = tagQuery.trim().toLowerCase()
  const tagOptions = (facets?.tags ?? [])
    .filter((t) => tags.includes(t.value) || !needle || t.value.toLowerCase().includes(needle))
    .sort((a, b) => Number(tags.includes(b.value)) - Number(tags.includes(a.value)))
  const shownTags = tagOptions.slice(0, Math.max(TAGS_SHOWN, tags.length))

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex gap-2">
        <div className="relative min-w-0 flex-1">
          <Icon name="search" className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-sub" />
          <DebouncedInput
            type="search"
            value={params.get("search") ?? ""}
            onCommit={(v) => update({ search: v.trim() || null })}
            placeholder="Name or number"
            aria-label="Search problems"
            maxLength={100}
            enterKeyHint="search"
            className={`${inputClass} pl-9`}
          />
        </div>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls={`${uid}-panel`}
          className={`${chipClass(open || panelCount > 0)} min-h-10 rounded-lg`}
        >
          <Icon name="filter" />
          <span className="max-sm:sr-only">Filters</span>
          {panelCount > 0 && <span className="num rounded-full bg-accent px-1.5 text-[11px] font-bold text-bg">{panelCount}</span>}
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Difficulty">
        {DIFFICULTIES.map((d) => {
          const active = difficulties.includes(d)
          const n = difficultyCount(d)
          return (
            <button key={d} type="button" aria-pressed={active} onClick={() => update({ difficulty: toggle(difficulties, d) })} className={chipClass(active)}>
              <span className={`h-2 w-2 rounded-full ${difficultyDot[d]}`} aria-hidden="true" />
              <span className="capitalize">{d}</span>
              {n !== undefined && <span className="num text-sub">{n}</span>}
            </button>
          )
        })}
      </div>

      {open && (
        <div id={`${uid}-panel`} className="flex flex-col gap-4 rounded-lg border border-input-border bg-bg/60 p-3">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-xs font-medium text-text">
              Tags {tags.length > 0 && <span className="text-sub">· all of {tags.length} selected</span>}
            </legend>
            <input
              type="search"
              value={tagQuery}
              onChange={(e) => setTagQuery(e.target.value)}
              placeholder="Find a tag"
              aria-label="Find a tag"
              className={inputClass}
            />
            <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
              {!facets && <span className="text-xs text-sub">Loading tags…</span>}
              {facets && shownTags.length === 0 && <span className="text-xs text-sub">No tag matches “{tagQuery}”.</span>}
              {shownTags.map((t) => (
                <button key={t.value} type="button" aria-pressed={tags.includes(t.value)} onClick={() => update({ tags: toggle(tags, t.value) })} className={chipClass(tags.includes(t.value))}>
                  {t.value}
                  <span className="num text-sub">{t.count}</span>
                </button>
              ))}
            </div>
          </fieldset>

          {facets && facets.sources.length > 1 && (
            <fieldset>
              <legend className="mb-2 text-xs font-medium text-text">Source</legend>
              <div className="flex flex-wrap gap-1.5">
                {facets.sources.map((s) => (
                  <button key={s.value} type="button" aria-pressed={sources.includes(s.value)} onClick={() => update({ source: toggle(sources, s.value) })} className={chipClass(sources.includes(s.value))}>
                    {s.label ?? s.value}
                    <span className="num text-sub">{s.count}</span>
                  </button>
                ))}
              </div>
            </fieldset>
          )}

          <fieldset>
            <legend className="mb-2 text-xs font-medium text-text">Codeforces rating</legend>
            <div className="flex items-center gap-2">
              <DebouncedInput
                type="number"
                inputMode="numeric"
                min={0}
                max={5000}
                step={100}
                value={params.get("rating_min") ?? ""}
                onCommit={(v) => update({ rating_min: rating(v) })}
                placeholder={facets?.rating.min ? `from ${facets.rating.min}` : "from"}
                aria-label="Minimum rating"
                className={inputClass}
                delay={600}
              />
              <span className="text-sub" aria-hidden="true">–</span>
              <DebouncedInput
                type="number"
                inputMode="numeric"
                min={0}
                max={5000}
                step={100}
                value={params.get("rating_max") ?? ""}
                onCommit={(v) => update({ rating_max: rating(v) })}
                placeholder={facets?.rating.max ? `to ${facets.rating.max}` : "to"}
                aria-label="Maximum rating"
                className={inputClass}
                delay={600}
              />
            </div>
            <p className="mt-1.5 text-xs text-sub">A range leaves out problems without a rating.</p>
          </fieldset>
        </div>
      )}
    </div>
  )
}

export const SortSelect = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
  <label className="flex items-center gap-1.5 text-xs text-sub">
    Sort
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="min-h-8 rounded-md border border-input-border bg-input-bg px-1.5 text-xs text-text hover:border-sub focus:border-accent focus:outline-none pointer-coarse:min-h-10"
    >
      {ORDERINGS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  </label>
)
