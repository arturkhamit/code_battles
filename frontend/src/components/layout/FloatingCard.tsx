import type { ReactNode } from "react"

type FloatingCardProps = {
  children: ReactNode
  className?: string
  title?: string
  /** right side of the title row */
  aside?: ReactNode
  "aria-label"?: string
}

export const FloatingCard = ({ children, className = "", title, aside, "aria-label": ariaLabel }: FloatingCardProps) => (
  <section
    className={`flex min-w-0 flex-col overflow-hidden rounded-xl border border-card-border bg-sub-alt p-4 sm:p-5 ${className}`}
    aria-label={ariaLabel ?? title}
  >
    {(title || aside) && (
      <div className="mb-3 flex items-center justify-between gap-3">
        {title && <h2 className="font-mono text-lg font-bold text-text">{title}</h2>}
        {aside}
      </div>
    )}
    {children}
  </section>
)
