import { useEffect, useState } from "react"
import { Link, Outlet, useLocation } from "react-router-dom"
import { useAuthContext } from "../../hooks/auth-context"
import { btn } from "../../lib/ui"
import { Icon } from "../ui/Icon"
import { Footer } from "./Footer"
import { Navbar } from "./Navbar"

export const Wordmark = () => (
  <Link to="/training" className="flex items-center gap-2 rounded-lg">
    <Icon name="logo" className="h-6 w-6 text-main" />
    <span className="font-mono text-lg font-bold text-text sm:text-xl">codebattles</span>
  </Link>
)

export const AppLayout = () => {
  const { auth, logout } = useAuthContext()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuPath, setMenuPath] = useState(location.pathname)
  if (menuPath !== location.pathname) {
    // a navigation closes the phone menu
    setMenuPath(location.pathname)
    setMenuOpen(false)
  }
  const username = auth.status === "authenticated" ? auth.user.username : ""

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false)
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [menuOpen])

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-main focus:px-3 focus:py-2 focus:text-bg">
        Skip to content
      </a>
      <header className="relative border-b border-card-border/60 px-4 pt-[env(safe-area-inset-top)] sm:px-6">
        <div className="flex h-14 items-center gap-4">
          <Wordmark />
          <nav aria-label="Main" className="hidden md:block">
            <Navbar />
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden max-w-48 items-center gap-2 text-sm text-sub sm:flex" title={username}>
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sub-alt text-xs font-bold text-text uppercase" aria-hidden="true">
                {username.slice(0, 2)}
              </span>
              <span className="truncate">{username}</span>
            </span>
            <button type="button" onClick={() => logout()} className={`${btn.ghost} px-2 sm:px-3`} aria-label={`Log out ${username}`}>
              <Icon name="logout" />
              <span className="hidden sm:inline">Log out</span>
            </button>
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              aria-label={menuOpen ? "Close menu" : "Open menu"}
              className={`${btn.ghost} px-2 md:hidden`}
            >
              <Icon name={menuOpen ? "x" : "menu"} className="h-5 w-5" />
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav id="mobile-nav" aria-label="Main" className="border-t border-card-border/60 py-3 md:hidden">
            <p className="mb-2 truncate px-3 text-xs text-sub">Signed in as {username}</p>
            <Navbar vertical />
          </nav>
        )}
      </header>

      <main id="main" className="flex flex-1 flex-col gap-4 px-4 py-4 sm:px-6">
        <Outlet />
      </main>

      <Footer />
    </div>
  )
}
