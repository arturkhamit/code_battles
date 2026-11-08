import { useState, useEffect, useRef, useCallback } from "react"

const format = (seconds: number) =>
  `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`

/** Counts down from the server's remaining_seconds on the local monotonic clock, so a wrong
 * clock on this computer does not matter. */
export const useTimer = () => {
  const [remaining, setRemaining] = useState<number | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const start = useCallback(
    (remainingSeconds: number) => {
      stop()
      const endsAt = performance.now() + remainingSeconds * 1000
      const update = () => {
        const left = Math.max(0, Math.ceil((endsAt - performance.now()) / 1000))
        setRemaining(left)
        if (left <= 0) stop()
      }
      update()
      intervalRef.current = setInterval(update, 250)
    },
    [stop],
  )

  useEffect(() => stop, [stop])

  return { remaining, label: format(remaining ?? 0), start, stop }
}
