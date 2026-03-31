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
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-ctp-base p-8 text-ctp-text">
          <div className="max-w-md rounded-xl border border-ctp-red bg-ctp-surface0 p-6 text-center shadow-lg">
            <h2 className="text-xl font-bold text-ctp-red">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-ctp-subtext0">
              {this.state.errorMessage}
            </p>
            <p className="mt-3 text-xs text-ctp-overlay0">
              The application encountered an unexpected error. Your backend
              services are unaffected.
            </p>
            <button
              type="button"
              onClick={this.handleRetry}
              className="mt-4 rounded bg-ctp-blue px-4 py-2 text-sm font-bold text-ctp-crust transition hover:bg-ctp-lavender"
              aria-label="Try again"
              tabIndex={0}
            >
              Try again
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
