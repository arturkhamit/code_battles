import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { FloatingCard } from "../components/layout/FloatingCard"
import { usePageTitle } from "../hooks/use-page-title"
import { rememberBattle, resolveInvite } from "../lib/battles"
import { btn } from "../lib/ui"

/** /join/:code -> /battle/:id?invite=code */
export const JoinPage = () => {
  usePageTitle("Joining a battle")
  const { code = "" } = useParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    resolveInvite(code).then((result) => {
      if (cancelled) return
      if (!result.ok) {
        setError(result.error.status === 404 ? "This invite link is not valid. It may be mistyped, or the battle is over." : result.error.message)
        return
      }
      const b = result.data
      rememberBattle(b.id, { invite: code, task: b.task.id, type: b.type })
      navigate(`/battle/${b.id}?invite=${encodeURIComponent(code)}`, { replace: true })
    })
    return () => {
      cancelled = true
    }
  }, [code, navigate])

  return (
    <FloatingCard className="mx-auto w-full max-w-xl items-start gap-3">
      <h1 className="text-lg font-semibold text-text">{error ? "Can't open this invite" : "Opening the invite…"}</h1>
      {error ? (
        <>
          <p className="text-sm text-error" role="alert">{error}</p>
          <Link to="/unranked" className={btn.primary}>Back to lobbies</Link>
        </>
      ) : (
        <div className="h-2 w-40 animate-pulse rounded bg-input-bg" aria-hidden="true" />
      )}
    </FloatingCard>
  )
}
