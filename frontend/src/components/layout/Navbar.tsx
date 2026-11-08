import { NavLink } from "react-router-dom"
import { Icon, type IconName } from "../ui/Icon"

const tabs: { to: string; label: string; icon: IconName; soon?: boolean }[] = [
  { to: "/training", label: "Training", icon: "book" },
  { to: "/unranked", label: "Unranked", icon: "lightning" },
  { to: "/ranked", label: "Ranked", icon: "swords", soon: true },
  { to: "/leaderboard", label: "Leaderboard", icon: "chart", soon: true },
]

export const Navbar = ({ vertical = false, onNavigate }: { vertical?: boolean; onNavigate?: () => void }) => (
  <ul className={vertical ? "flex flex-col gap-1" : "flex items-center gap-1"}>
    {tabs.map((tab) => (
      <li key={tab.to}>
        <NavLink
          to={tab.to}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-medium transition ${
              isActive ? "bg-sub-alt text-text" : "text-sub hover:text-text"
            }`
          }
        >
          <Icon name={tab.icon} />
          {tab.label}
          {tab.soon && <span className="rounded bg-input-bg px-1.5 py-px text-[11px] font-medium text-sub">Soon</span>}
        </NavLink>
      </li>
    ))}
  </ul>
)
