import type { BattlePhase } from "../types/battle"

type HeaderProps = {
  timerLabel: string
  phase: BattlePhase
}

const phaseLabels: Record<BattlePhase, string> = {
  idle: "00:00",
  creating: "...",
  joining: "...",
  lobby: "LOBBY",
  active: "",
  finished: "FINISHED",
}

export const Header = ({ timerLabel, phase }: HeaderProps) => {
  const display =
    phase === "active" ? timerLabel : phaseLabels[phase]

  return (
    <header className="text-center">
      <h1 className="text-3xl font-bold text-ctp-blue">Code Battle Arena</h1>
      <div
        className="mt-1 font-mono text-2xl font-bold text-ctp-red"
        aria-live="polite"
        aria-label={`Timer: ${display}`}
      >
        {display}
      </div>
    </header>
  )
}
