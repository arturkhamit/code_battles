// One set of control styles for every screen: 40px controls (44px on touch), 8px radius.
const control = "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition select-none disabled:cursor-not-allowed disabled:opacity-50 pointer-coarse:min-h-11"

export const btn = {
  primary: `${control} bg-main text-bg hover:bg-main-hover`,
  secondary: `${control} border border-input-border bg-input-bg text-text hover:border-sub`,
  ghost: `${control} text-sub hover:bg-input-bg hover:text-text`,
  danger: `${control} border border-error/40 text-error hover:bg-error/10`,
  small: "inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md px-3 text-xs font-semibold transition select-none disabled:cursor-not-allowed disabled:opacity-50 pointer-coarse:min-h-10",
}

export const inputClass =
  "w-full min-h-10 rounded-lg border border-input-border bg-input-bg px-3 text-sm text-text transition placeholder:text-sub hover:border-sub focus:border-accent focus:outline-none disabled:opacity-60 aria-invalid:border-error pointer-coarse:min-h-11"

export const chipClass = (active: boolean) =>
  `inline-flex min-h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition select-none pointer-coarse:min-h-10 ${
    active
      ? "border-accent bg-accent/15 text-text"
      : "border-input-border text-sub hover:border-sub hover:text-text"
  }`

/** aria props for the control inside a Field (components/ui/Field.tsx). */
export const describedBy = (id: string, hasHelp: boolean, errors?: string[]) => {
  const ids = [hasHelp && `${id}-help`, errors?.length && `${id}-error`].filter(Boolean).join(" ")
  return {
    id,
    "aria-describedby": ids || undefined,
    "aria-invalid": errors?.length ? true : undefined,
  }
}

export const difficultyText: Record<string, string> = {
  easy: "text-main",
  medium: "text-yellow",
  hard: "text-error",
  unknown: "text-sub",
}

export const difficultyDot: Record<string, string> = {
  easy: "bg-main",
  medium: "bg-yellow",
  hard: "bg-error",
  unknown: "bg-sub",
}
