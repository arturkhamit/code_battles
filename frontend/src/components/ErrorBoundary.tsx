import { Component, type ErrorInfo, type ReactNode } from "react"

type Props = {
  children: ReactNode
}

type State = {
  hasError: boolean
  errorMessage: string
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, errorMessage: "" }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorMessage: error.message || "An unexpected error occurred",
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ hasError: false, errorMessage: "" })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg p-8 text-text">
          <div className="max-w-md rounded-xl border border-error bg-sub-alt p-6 text-center">
            <h2 className="text-xl font-bold text-error">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-sub">
              {this.state.errorMessage}
            </p>
            <p className="mt-3 text-xs text-sub">
              This page hit an error. Your account and battles are safe; reloading usually fixes it.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="rounded-lg bg-main px-4 py-2 text-sm font-bold text-bg transition hover:bg-main-hover"
              >
                Reload the page
              </button>
              <button
                type="button"
                onClick={this.handleRetry}
                className="rounded-lg border border-input-border px-4 py-2 text-sm font-medium text-text transition hover:border-sub"
              >
                Try again
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
