import { useEffect, useState, type InputHTMLAttributes } from "react"

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & {
  value: string
  onCommit: (value: string) => void
  delay?: number
}

/** Typed text goes to onCommit after a pause (or at once on Enter); outside changes win. */
export const DebouncedInput = ({ value, onCommit, delay = 300, onKeyDown, ...rest }: Props) => {
  const [draft, setDraft] = useState(value)
  const [synced, setSynced] = useState(value)
  if (value !== synced) {
    // the URL changed (reset, back button): show it
    setSynced(value)
    setDraft(value)
  }

  useEffect(() => {
    if (draft === value) return
    const t = setTimeout(() => onCommit(draft), delay)
    return () => clearTimeout(t)
  }, [draft, value, delay, onCommit])

  return (
    <input
      {...rest}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault()
          if (draft !== value) onCommit(draft)
        }
        onKeyDown?.(e)
      }}
    />
  )
}
