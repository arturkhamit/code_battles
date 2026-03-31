import { useState, useEffect, useRef, useCallback } from "react"

export const useTimer = () => {
  const [remaining, setRemaining] = useState<number | null>(null)
  const [label, setLabel] = useState("00:00")
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const start = useCallback(
    (deadlineUnix: number) => {
      stop()
      const update = () => {
        const now = Math.floor(Date.now() / 1000)
        const left = Math.max(0, Math.floor(deadlineUnix) - now)
        setRemaining(left)
        const m = String(Math.floor(left / 60)).padStart(2, "0")
        const s = String(left % 60).padStart(2, "0")
        setLabel(`${m}:${s}`)
        if (left <= 0) stop()
      }
      update()
      intervalRef.current = setInterval(update, 1000)
    },
    [stop],
  )

  const reset = useCallback(() => {
    stop()
    setRemaining(null)
    setLabel("00:00")
  }, [stop])

  useEffect(() => stop, [stop])

  return { remaining, label, start, stop, reset }
}
