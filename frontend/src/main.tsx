import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { App } from "./App"
import { ErrorBoundary } from "./components/ErrorBoundary"
import "./globals.css"

window.onerror = (message, _source, _line, _col, _error) => {
  console.error("[Global Error]", message)
  return true
}

window.addEventListener("unhandledrejection", (event) => {
  console.error("[Unhandled Promise Rejection]", event.reason)
  event.preventDefault()
})

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
