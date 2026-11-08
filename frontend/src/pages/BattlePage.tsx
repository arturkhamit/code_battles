import { useEffect, useRef, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { CodePanel } from "../components/CodePanel"
import { ErrorBanner } from "../components/ErrorBanner"
import { FloatingCard } from "../components/layout/FloatingCard"
import { LogPanel } from "../components/LogPanel"
import { TaskPanel } from "../components/TaskPanel"
import { Icon } from "../components/ui/Icon"
import { useAuthContext } from "../hooks/auth-context"
import { useBattle } from "../hooks/use-battle"
import { usePageTitle } from "../hooks/use-page-title"
import { battleLink, getKnownBattle, rememberBattle } from "../lib/battles"
import { btn } from "../lib/ui"
import type { BattleResult, BattleState } from "../types/battle"

const InviteLink = ({ link }: { link: string }) => {
  const inputRef = useRef<HTMLInputElement>(null)
  const [hint, setHint] = useState("")

  const handleCopy = async () => {
    try {
      // plain HTTP (no secure context) has no clipboard API
      if (!window.isSecureContext || !navigator.clipboard) throw new Error("no clipboard")
      await navigator.clipboard.writeText(link)
      setHint("Copied!")
    } catch {
      inputRef.current?.select()
      setHint("Press Ctrl+C to copy the selected link.")
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="invite-link" className="text-xs font-medium text-sub">Invite link</label>
      <div className="flex">
        <input
          id="invite-link"
          ref={inputRef}
          readOnly
          value={link}
          onFocus={(e) => e.currentTarget.select()}
          className="min-h-10 min-w-0 flex-1 rounded-l-lg border border-input-border bg-input-bg px-3 font-mono text-xs text-text focus:border-accent focus:outline-none"
          aria-label="Invite link"
        />
        <button type="button" onClick={handleCopy} className={`${btn.secondary} rounded-l-none border-l-0`} aria-label="Copy invite link">
          <Icon name="copy" />
          Copy
        </button>
      </div>
      <span className="min-h-4 text-xs text-main" aria-live="polite">{hint}</span>
    </div>
  )
}

const Fact = ({ label, value }: { label: string; value: string }) => (
  <div className="min-w-0">
    <dt className="text-xs text-sub">{label}</dt>
    <dd className="num truncate text-sm font-medium text-text">{value}</dd>
  </div>
)

const LobbyCard = ({ state, battleId, inviteCode, onStart }: { state: BattleState; battleId: number; inviteCode?: string; onStart: () => void }) => {
  const players = state.participantsCount ?? 0
  const max = state.facts?.maxParticipants
  const canStart = state.isCreator && !state.isSpectator && players >= 2
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-input-border bg-bg/60 p-4">
      <p className="text-sm text-yellow">
        Lobby · {players}/{max ?? "?"} players
        {state.isCreator
          ? players < 2
            ? " · share the link, you can start when a second player is in"
            : " · ready when you are"
          : " · waiting for the creator to start"}
      </p>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Fact label="Type" value={state.facts?.type === "group" ? "Group" : "1v1 duel"} />
        <Fact label="Duration" value={state.facts?.durationMinutes ? `${Math.round(state.facts.durationMinutes)} min` : "—"} />
        <Fact label="Players" value={`${players} of ${max ?? "?"}`} />
        <Fact label="Created by" value={state.isCreator ? "You" : state.facts?.creatorName ?? "—"} />
      </dl>
      <InviteLink link={battleLink(battleId, inviteCode)} />
      {canStart && (
        <button type="button" onClick={onStart} className={btn.primary} aria-label="Start battle">
          <Icon name="play" />
          Start battle
        </button>
      )}
    </div>
  )
}

const ResultCard = ({ result, userId, isSpectator, taskId }: { result: BattleResult; userId: number; isSpectator: boolean; taskId: number | null }) => {
  const won = result.winnerId !== null && result.winnerId === userId
  const draw = result.winnerId === null
  const title = draw ? "Draw" : won ? "Victory" : isSpectator ? `${result.winnerName ?? "A player"} won` : "Defeat"
  const line = draw
    ? result.reason === "time_up" ? "Time ran out before anyone passed every test." : "The battle ended without a winner."
    : won
      ? "Your solution passed every test first."
      : `${result.winnerName ?? "Your opponent"} passed every test first.`
  return (
    <div className={`flex flex-col gap-3 rounded-lg border p-4 ${won ? "border-main/60 bg-main/10" : draw ? "border-yellow/50 bg-yellow/5" : "border-input-border bg-bg/60"}`}>
      <div>
        <p className={`font-mono text-2xl font-bold ${won ? "text-main" : draw ? "text-yellow" : "text-text"}`}>{title}</p>
        <p className="text-sm text-sub">{line}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link to={taskId ? `/unranked?task=${taskId}` : "/unranked"} className={btn.primary}>
          New battle
        </Link>
        <Link to="/unranked" className={btn.secondary}>
          Back to lobbies
        </Link>
        <Link to={taskId ? `/training?task=${taskId}` : "/training"} className={btn.ghost}>
          Practice this task
        </Link>
      </div>
    </div>
  )
}

type BattleViewProps = { battleId: number; role?: string; invite?: string; userId: number }

const BattleView = ({ battleId, role, invite, userId }: BattleViewProps) => {
  const [known] = useState(() => getKnownBattle(battleId))
  const battle = useBattle({ battleId, role, invite }, userId)
  const { state, taskInfo, timer } = battle
  usePageTitle(state.phase === "active" ? `${timer.label} · Battle #${battleId}` : `Battle #${battleId}`)

  useEffect(() => {
    if (invite) rememberBattle(battleId, { invite })
  }, [battleId, invite])

  const inviteCode = known.invite ?? invite
  const type = state.facts?.type ?? known.type
  const watchLink = `/battle/${battleId}?role=spectator${inviteCode ? `&invite=${encodeURIComponent(inviteCode)}` : ""}`
  const phaseLabel = { connecting: "Connecting…", lobby: "Lobby", active: "Live", finished: "Finished", closed: "Disconnected" }[state.phase]

  return (
    <div className="flex flex-1 flex-col gap-4">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-card-border bg-sub-alt px-4 py-3">
        <h1 className="font-mono text-base font-bold text-text">
          Battle <span className="num">#{battleId}</span>
          {type && <span className="ml-2 text-sm font-normal text-sub">{type === "1v1" ? "1v1" : "Group"}</span>}
        </h1>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.phase === "active" ? "bg-error/15 text-error" : state.phase === "lobby" ? "bg-yellow/10 text-yellow" : state.phase === "finished" ? "bg-main/10 text-main" : "bg-input-bg text-sub"}`}>
          {phaseLabel}
        </span>
        {state.phase === "active" && (
          <span className="num inline-flex items-center gap-1.5 font-mono text-lg font-bold text-text" aria-label="Time left" role="timer">
            {timer.label}
          </span>
        )}
        {state.participantsCount !== null && (
          <span className="num inline-flex items-center gap-1 text-xs text-sub">
            <Icon name="users" className="h-3.5 w-3.5" />
            {state.participantsCount}/{state.facts?.maxParticipants ?? "?"} players
          </span>
        )}
        {state.isSpectator && (
          <span className="inline-flex items-center gap-1 text-xs text-sub">
            <Icon name="eye" className="h-3.5 w-3.5" />
            You are watching
          </span>
        )}
        <Link to="/unranked" className={`${btn.small} ml-auto border border-error/40 text-error hover:bg-error/10`} aria-label="Leave the battle">
          Leave
        </Link>
      </header>

      {state.closed && (
        <div role="alert" className="rounded-lg border border-error/60 bg-error/10 p-3 text-sm text-error">
          <p className="font-semibold">{state.closed.message}</p>
          <div className="mt-2 flex flex-wrap gap-3 text-xs">
            {state.closed.code === 4409 && role !== "spectator" && (
              <Link to={watchLink} className="font-bold underline">Watch as a spectator</Link>
            )}
            {state.closed.code === 4001 && (
              <button type="button" onClick={() => window.location.reload()} className="font-bold underline">Use this tab</button>
            )}
            <Link to="/unranked" className="underline">Back to lobbies</Link>
          </div>
        </div>
      )}
      {state.error && <ErrorBanner error={state.error} onDismiss={battle.clearError} />}

      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[1fr_1.3fr] xl:h-[calc(100dvh-12rem)] xl:min-h-[34rem] xl:flex-none xl:grid-cols-[1fr_1.3fr_18rem]">
        <FloatingCard aria-label="Task" className="max-h-[70dvh] lg:max-h-none xl:min-h-0">
          <TaskPanel task={taskInfo} phase={state.phase} />
        </FloatingCard>

        <FloatingCard aria-label="Your solution" className="gap-4 xl:min-h-0">
          {state.phase === "lobby" && (
            <LobbyCard state={state} battleId={battleId} inviteCode={inviteCode} onStart={battle.handleStart} />
          )}
          {state.result && (
            <ResultCard result={state.result} userId={userId} isSpectator={state.isSpectator} taskId={state.taskId} />
          )}
          <CodePanel
            phase={state.phase}
            isSpectator={state.isSpectator}
            submitStatus={state.submitStatus}
            onSubmit={battle.handleSubmit}
            draftKey={`cb_battle_${battleId}`}
          />
        </FloatingCard>

        <FloatingCard title="Battle log" className="min-h-80 lg:col-span-2 xl:col-span-1 xl:min-h-0">
          <LogPanel logs={state.logs} phase={state.phase} onSendChat={battle.handleChat} />
        </FloatingCard>
      </div>
    </div>
  )
}

export const BattlePage = () => {
  const { auth } = useAuthContext()
  const { id } = useParams()
  const [params] = useSearchParams()
  const battleId = Number(id)
  const role = params.get("role") ?? undefined
  const invite = params.get("invite") ?? undefined
  const userId = auth.status === "authenticated" ? auth.user.id : 0

  if (!Number.isInteger(battleId) || battleId <= 0) {
    return (
      <FloatingCard className="flex-1 items-start gap-3">
        <h1 className="text-lg font-semibold text-text">This battle link is broken</h1>
        <p className="text-sm text-sub">A battle link looks like /battle/42. Ask for the link again or pick an open lobby.</p>
        <Link to="/unranked" className={btn.primary}>Back to lobbies</Link>
      </FloatingCard>
    )
  }

  // a new battle, role or invite is a new connection with a fresh state
  return <BattleView key={`${battleId}:${role}:${invite}`} battleId={battleId} role={role} invite={invite} userId={userId} />
}
