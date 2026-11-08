import { difficultyDot, difficultyText } from "../../lib/ui"

/** Colour plus the word, so the difficulty never rests on colour alone. */
export const DifficultyBadge = ({ label, rating }: { label: string; rating?: number | null }) => (
  <span className={`inline-flex shrink-0 items-center gap-1.5 text-xs font-semibold ${difficultyText[label] ?? "text-sub"}`}>
    <span className={`inline-block h-2 w-2 rounded-full ${difficultyDot[label] ?? "bg-sub"}`} title={label} aria-hidden="true" />
    <span className="capitalize">{label}</span>
    {rating ? <span className="num font-normal text-sub">· {rating}</span> : null}
  </span>
)
