import type { BattlePhase, BattleType } from "../types/battle"

type ControlsProps = {
  phase: BattlePhase
  username: string
  taskId: number
  battleType: BattleType
  duration: number
  maxParticipants: number
  battleId: number | null
  canShowStart: boolean
  fieldErrors?: Record<string, string[]>
  onTaskIdChange: (v: number) => void
  onBattleTypeChange: (v: BattleType) => void
  onDurationChange: (v: number) => void
  onMaxParticipantsChange: (v: number) => void
  onBattleIdChange: (v: number) => void
  onCreate: () => void
  onJoin: () => void
  onStart: () => void
  onDisconnect: () => void
  onLogout: () => void
}

const hasFieldError = (
  fieldErrors: Record<string, string[]> | undefined,
  ...fields: string[]
) => {
  if (!fieldErrors) return false
  return fields.some((f) => fieldErrors[f]?.length)
}

const inputClass = (hasError: boolean) =>
  `w-16 rounded border bg-ctp-crust px-2 py-1.5 text-sm text-ctp-text outline-none transition ${
    hasError
      ? "border-ctp-red ring-1 ring-ctp-red"
      : "border-ctp-surface1 focus:border-ctp-blue"
  }`

export const Controls = ({
  phase,
  username,
  taskId,
  battleType,
  duration,
  maxParticipants,
  battleId,
  canShowStart,
  fieldErrors,
  onTaskIdChange,
  onBattleTypeChange,
  onDurationChange,
  onMaxParticipantsChange,
  onBattleIdChange,
  onCreate,
  onJoin,
  onStart,
  onDisconnect,
  onLogout,
}: ControlsProps) => {
  const isConnected =
    phase === "lobby" || phase === "active" || phase === "finished"
  const isIdle = phase === "idle"
  const isBusy = phase === "creating" || phase === "joining"

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg bg-ctp-mantle p-3">
      <span
        className="flex items-center gap-1.5 rounded bg-ctp-surface0 px-2.5 py-1.5 text-sm font-medium text-ctp-lavender"
        aria-label={`Logged in as ${username}`}
      >
        {username}
      </span>

      <div className="h-7 w-px bg-ctp-surface1" />

      <label className="flex items-center gap-1.5 text-sm">
        Task ID:
        <input
          type="number"
          value={taskId}
          onChange={(e) => onTaskIdChange(Number(e.target.value))}
          disabled={isConnected || isBusy}
          className={inputClass(hasFieldError(fieldErrors, "task"))}
          aria-label="Task ID"
          min={1}
        />
      </label>

      <label className="flex items-center gap-1.5 text-sm">
        Type:
        <select
          value={battleType}
          onChange={(e) => onBattleTypeChange(e.target.value as BattleType)}
          disabled={isConnected || isBusy}
          className="rounded border border-ctp-surface1 bg-ctp-crust px-2 py-1.5 text-sm text-ctp-text outline-none transition focus:border-ctp-blue"
          aria-label="Battle type"
        >
          <option value="1v1">1v1</option>
          <option value="group">Group</option>
        </select>
      </label>

      <label className="flex items-center gap-1.5 text-sm">
        Duration (min):
        <input
          type="number"
          value={duration}
          onChange={(e) => onDurationChange(Number(e.target.value))}
          disabled={isConnected || isBusy}
          className={inputClass(hasFieldError(fieldErrors, "duration"))}
          aria-label="Duration in minutes"
          min={1}
        />
      </label>

      {battleType === "group" && (
        <label className="flex items-center gap-1.5 text-sm">
          Max Players:
          <input
            type="number"
            value={maxParticipants}
            onChange={(e) => onMaxParticipantsChange(Number(e.target.value))}
            disabled={isConnected || isBusy}
            className={inputClass(hasFieldError(fieldErrors, "max_participants"))}
            aria-label="Maximum number of players"
            min={2}
            max={50}
          />
        </label>
      )}

      <div className="h-7 w-px bg-ctp-surface1" />

      <button
        type="button"
        onClick={onCreate}
        disabled={!isIdle || isBusy}
        className="rounded bg-ctp-green px-3 py-1.5 text-sm font-bold text-ctp-crust transition hover:bg-ctp-teal disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
        aria-label="Create battle"
        tabIndex={0}
      >
        {phase === "creating" ? "Creating..." : "Create Battle"}
      </button>

      <div className="h-7 w-px bg-ctp-surface1" />

      <label className="flex items-center gap-1.5 text-sm">
        Battle ID:
        <input
          type="number"
          value={battleId ?? ""}
          onChange={(e) => onBattleIdChange(Number(e.target.value))}
          disabled={isConnected || isBusy}
          placeholder="ID"
          className={inputClass(hasFieldError(fieldErrors, "battle_id"))}
          aria-label="Battle ID"
          min={1}
        />
      </label>

      <button
        type="button"
        onClick={onJoin}
        disabled={!isIdle || isBusy}
        className="rounded bg-ctp-blue px-3 py-1.5 text-sm font-bold text-ctp-crust transition hover:bg-ctp-lavender disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
        aria-label="Join battle"
        tabIndex={0}
      >
        Join Battle
      </button>

      {canShowStart && (
        <>
          <div className="h-7 w-px bg-ctp-surface1" />
          <button
            type="button"
            onClick={onStart}
            className="rounded bg-ctp-yellow px-3 py-1.5 text-sm font-bold text-ctp-crust transition hover:bg-ctp-pink"
            aria-label="Start battle"
            tabIndex={0}
          >
            ▶ Start Battle!
          </button>
        </>
      )}

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onDisconnect}
          disabled={!isConnected}
          className="rounded bg-ctp-red px-3 py-1.5 text-sm font-bold text-ctp-crust transition hover:bg-ctp-pink disabled:cursor-not-allowed disabled:bg-ctp-surface1 disabled:text-ctp-subtext0"
          aria-label="Disconnect"
          tabIndex={0}
        >
          Disconnect
        </button>

        <button
          type="button"
          onClick={onLogout}
          disabled={isConnected}
          className="rounded border border-ctp-surface1 bg-ctp-surface0 px-3 py-1.5 text-sm font-medium text-ctp-subtext1 transition hover:border-ctp-red hover:text-ctp-red disabled:cursor-not-allowed disabled:opacity-40"
          aria-label="Logout"
          tabIndex={0}
        >
          Logout
        </button>
      </div>
    </div>
  )
}
