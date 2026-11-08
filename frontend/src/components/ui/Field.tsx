import type { ReactNode } from "react"

type FieldProps = {
  id: string
  label: string
  help?: ReactNode
  errors?: string[]
  children: ReactNode
}

/** Label above, help and errors below, tied to the control by id-help / id-error. */
export const Field = ({ id, label, help, errors, children }: FieldProps) => (
  <div className="flex flex-col gap-1.5">
    <label htmlFor={id} className="text-sm font-medium text-text">
      {label}
    </label>
    {children}
    {help && (
      <div id={`${id}-help`} className="text-xs leading-relaxed text-sub">
        {help}
      </div>
    )}
    {errors && errors.length > 0 && (
      <p id={`${id}-error`} className="text-xs font-medium text-error" role="alert">
        {errors.join(" ")}
      </p>
    )}
  </div>
)
