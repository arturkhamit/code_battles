import type { ApiErrorState } from "../types/battle"

type ErrorBannerProps = {
  error: ApiErrorState
  onDismiss: () => void
}

export const ErrorBanner = ({ error, onDismiss }: ErrorBannerProps) => {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-ctp-red bg-ctp-red/10 p-3 text-sm text-ctp-red"
    >
      <div className="flex-1">
        <p className="font-semibold">{error.message}</p>
        {error.fieldErrors && Object.keys(error.fieldErrors).length > 0 && (
          <ul className="mt-1 list-inside list-disc text-xs">
            {Object.entries(error.fieldErrors).map(([field, msgs]) => (
              <li key={field}>
                <span className="font-medium">{field}:</span> {msgs.join(", ")}
              </li>
            ))}
          </ul>
        )}
        {error.isHtml && (
          <p className="mt-1 text-xs text-ctp-subtext0">
            The server returned an HTML page instead of JSON. This usually
            indicates a server-side error.
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 rounded px-2 py-1 text-xs font-bold text-ctp-red transition hover:bg-ctp-red/20"
        aria-label="Dismiss error"
        tabIndex={0}
      >
        Dismiss
      </button>
    </div>
  )
}
