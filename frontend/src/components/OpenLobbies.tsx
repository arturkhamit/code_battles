import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { fetchOpenBattles, rememberBattle } from "../lib/battles"
import { btn } from "../lib/ui"
import type { ApiErrorState, OpenBattle } from "../types/battle"
import { ErrorBanner } from "./ErrorBanner"
import { FloatingCard } from "./layout/FloatingCard"
import { DifficultyBadge } from "./ui/DifficultyBadge"
import { Icon } from "./ui/Icon"

const LOBBY_PAGE = 10

export const OpenLobbies = () => {
  const [offset, setOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [page, setPage] = useState<{ key: string; count: number; results: OpenBattle[] } | null>(null)
  const [error, setError] = useState<ApiErrorState | null>(null)
  const key = `${offset}:${reload}`

  useEffect(() => {
    let cancelled = false
    fetchOpenBattles(LOBBY_PAGE, offset).then((result) => {
      if (cancelled) return
      if (result.ok) {
        setPage({ key: `${offset}:${reload}`, ...result.data })
        setError(null)
      } else {
        setError(result.error)
      }
    })
    return () => {
      cancelled = true
    }
  }, [offset, reload])

  const loading = page?.key !== key && !error
  const remember = (b: OpenBattle) => rememberBattle(b.id, { task: b.task.id, type: b.type })

  return (
    <FloatingCard
      title="Open lobbies"
      aside={
        <button type="button" onClick={() => setReload((n) => n + 1)} className={`${btn.small} text-sub hover:text-text`} aria-label="Refresh open lobbies">
          <Icon name="refresh" className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      }
    >
      {error && <ErrorBanner error={error} onDismiss={() => setError(null)} />}
      {!page && !error && <p className="text-sm text-sub">Loading lobbies…</p>}
      {page?.results.length === 0 && (
        <p className="text-sm text-sub">No open lobbies right now. Create a battle and share its link.</p>
      )}
      <ul className="flex flex-col gap-2">
        {page?.results.map((b) => (
          <li key={b.id} className="flex flex-col gap-1.5 rounded-lg bg-bg p-3" data-testid="lobby">
            <div className="flex items-start justify-between gap-2">
              <span className="line-clamp-2 min-w-0 text-sm font-medium break-words text-text">
                {b.task.name ?? `Task ${b.task.id}`}
              </span>
              <DifficultyBadge label={b.task.difficulty_label} />
            </div>
            <div className="num flex min-w-0 gap-1 text-xs text-sub">
              <span className="shrink-0">
                #{b.id} · {b.type === "1v1" ? "1v1" : "Group"} · {b.duration} min ·
              </span>
              <span className="min-w-0 truncate" title={b.creator_username}>by {b.creator_username}</span>
            </div>
            <div className="flex items-center justify-between gap-2">
              <span className="num inline-flex items-center gap-1 text-xs text-sub">
                <Icon name="users" className="h-3.5 w-3.5" />
                {b.players_count}/{b.max_participants} players
              </span>
              <span className="flex gap-1.5">
                <Link to={`/battle/${b.id}?role=spectator`} onClick={() => remember(b)} className={`${btn.small} text-sub hover:text-text`}>
                  <Icon name="eye" className="h-3.5 w-3.5" />
                  Watch
                </Link>
                {b.players_count >= b.max_participants ? (
                  <span className={`${btn.small} cursor-default border border-input-border text-sub`}>Full</span>
                ) : (
                  <Link to={`/battle/${b.id}?role=player`} onClick={() => remember(b)} className={`${btn.small} bg-main text-bg hover:bg-main-hover`}>
                    <Icon name="play" className="h-3.5 w-3.5" />
                    Play
                  </Link>
                )}
              </span>
            </div>
          </li>
        ))}
      </ul>
      {page && page.count > LOBBY_PAGE && (
        <nav className="mt-3 flex items-center justify-between text-xs text-sub" aria-label="Lobby pages">
          <button type="button" disabled={offset === 0} onClick={() => setOffset((o) => Math.max(0, o - LOBBY_PAGE))} className={`${btn.small} hover:text-text`}>
            Previous
          </button>
          <span className="num">
            {offset + 1}–{Math.min(offset + LOBBY_PAGE, page.count)} of {page.count}
          </span>
          <button type="button" disabled={offset + LOBBY_PAGE >= page.count} onClick={() => setOffset((o) => o + LOBBY_PAGE)} className={`${btn.small} hover:text-text`}>
            Next
          </button>
        </nav>
      )}
    </FloatingCard>
  )
}
