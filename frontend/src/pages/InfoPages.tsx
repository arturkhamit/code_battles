import type { ReactNode } from "react"
import { Link } from "react-router-dom"
import { Wordmark } from "../components/layout/AppLayout"
import { FloatingCard } from "../components/layout/FloatingCard"
import { useAuthContext } from "../hooks/auth-context"
import { usePageTitle } from "../hooks/use-page-title"
import { btn } from "../lib/ui"

const Prose = ({ title, children }: { title: string; children: ReactNode }) => {
  usePageTitle(title)
  return (
    <FloatingCard className="mx-auto w-full max-w-2xl">
      <h1 className="mb-4 text-2xl font-semibold text-text">{title}</h1>
      <div className="flex flex-col gap-3 text-sm leading-relaxed text-text/90 [&_h2]:mt-3 [&_h2]:font-semibold [&_h2]:text-text">{children}</div>
    </FloatingCard>
  )
}

const ComingSoon = ({ title, text }: { title: string; text: string }) => {
  usePageTitle(title)
  return (
    <FloatingCard className="mx-auto w-full max-w-xl items-start gap-3">
      <span className="rounded bg-input-bg px-2 py-0.5 text-xs font-medium text-sub">Coming soon</span>
      <h1 className="text-2xl font-semibold text-text">{title}</h1>
      <p className="text-sm leading-relaxed text-sub">{text}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Link to="/unranked" className={btn.primary}>Play an unranked battle</Link>
        <Link to="/training" className={btn.secondary}>Train on problems</Link>
      </div>
    </FloatingCard>
  )
}

export const RankedPage = () => (
  <ComingSoon title="Ranked battles" text="Ranked matchmaking with an ELO rating is not open yet. Until then, unranked battles use the same tasks and rules, without changing anyone's rating." />
)

export const LeaderboardPage = () => (
  <ComingSoon title="Leaderboard" text="The leaderboard opens together with ranked battles, once ratings exist to rank." />
)

export const SuggestionsPage = () => (
  <ComingSoon title="Task suggestions" text="Proposing your own problems is planned. For now the catalog holds the code_contests problem set." />
)

export const AboutPage = () => (
  <Prose title="About codebattles">
    <p>codebattles is a place to practise competitive programming and to race other people on the same problem.</p>
    <h2>Training</h2>
    <p>Pick any of the problems in the catalog, read the statement and examples, and submit Python 3 or C++ code. The judge runs it against the public and hidden tests and tells you which test failed.</p>
    <h2>Battles</h2>
    <p>Create a 1v1 duel or a group battle on a task, share the invite link, and start when everyone is in. The first player whose code passes every test wins; when time runs out with no accepted solution, the battle is a draw. Anyone with the link can watch.</p>
    <h2>Problems</h2>
    <p>The tasks come from the public code_contests dataset (Codeforces, CodeChef, AtCoder and others), with their original limits and difficulty ratings.</p>
  </Prose>
)

export const SecurityPage = () => (
  <Prose title="Security">
    <p>How this site treats your account and your code.</p>
    <h2>Accounts</h2>
    <p>Passwords are stored only as salted hashes. Sign-in uses short-lived access tokens that are refreshed in the background; logging out revokes the refresh token.</p>
    <h2>Your code</h2>
    <p>Submissions run in an isolated sandbox with no network access and with time and memory limits. Hidden tests never leave the server: a failed hidden test is reported by its number only.</p>
    <h2>Limits</h2>
    <p>Sign-in, sign-up, submissions and battle actions are rate-limited to keep the judge fair. If you hit a limit, the page tells you how long to wait.</p>
    <h2>Reporting a problem</h2>
    <p>If you find a vulnerability, please report it privately to the people who run this site rather than in a public channel.</p>
  </Prose>
)

export const NotFoundPage = () => {
  usePageTitle("Page not found")
  const { auth } = useAuthContext()
  const signedIn = auth.status === "authenticated"
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-6 bg-bg p-6 text-center">
      <Wordmark />
      <div className="flex max-w-md flex-col items-center gap-2">
        <p className="num font-mono text-5xl font-bold text-sub">404</p>
        <h1 className="text-xl font-semibold text-text">This page does not exist</h1>
        <p className="text-sm text-sub">The link may be mistyped, or the page has moved. Battle links look like /battle/42.</p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <Link to={signedIn ? "/training" : "/login"} className={btn.primary}>
          {signedIn ? "Go to training" : "Sign in"}
        </Link>
        {signedIn && <Link to="/unranked" className={btn.secondary}>Open lobbies</Link>}
      </div>
    </div>
  )
}
