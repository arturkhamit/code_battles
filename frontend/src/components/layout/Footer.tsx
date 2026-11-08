import { Link } from "react-router-dom"
import { CONFIG } from "../../config"

const linkClass = "rounded px-1 py-1 transition hover:text-text"

// GitHub and contact appear only when the deployment sets them (VITE_GITHUB_URL, VITE_CONTACT_EMAIL)
export const Footer = () => (
  <footer className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1 px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] text-xs text-sub">
    <Link to="/about" className={linkClass}>About</Link>
    <Link to="/security" className={linkClass}>Security</Link>
    {CONFIG.GITHUB_URL && (
      <a href={CONFIG.GITHUB_URL} target="_blank" rel="noreferrer" className={linkClass}>
        GitHub
      </a>
    )}
    {CONFIG.CONTACT_EMAIL && (
      <a href={`mailto:${CONFIG.CONTACT_EMAIL}`} className={linkClass}>
        Contact
      </a>
    )}
  </footer>
)
