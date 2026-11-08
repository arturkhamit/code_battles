import { CONFIG } from "../config"

export type ApiError = {
  message: string
  fieldErrors?: Record<string, string[]>
  status: number
  isHtml: boolean
  retryAfter?: number
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError }

const extractHtmlMessage = (html: string): string => {
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i)
  if (titleMatch) return titleMatch[1].trim()

  const h1Match = html.match(/<h1[^>]*>([^<]+)<\/h1>/i)
  if (h1Match) return h1Match[1].trim()

  const textOnly = html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()
  return textOnly.slice(0, 200) || "Unknown server error"
}

const formatDrfErrors = (
  body: Record<string, unknown>,
): { message: string; fieldErrors: Record<string, string[]> } => {
  const fieldErrors: Record<string, string[]> = {}
  const messages: string[] = []

  for (const [key, value] of Object.entries(body)) {
    // FastAPI 429: {detail, code, scope, retry_after}; only detail is for people
    if (typeof body.detail === "string" && ["code", "scope", "retry_after"].includes(key)) continue
    const errors = Array.isArray(value) ? value.map(String) : [String(value)]

    if (key === "non_field_errors" || key === "detail" || key === "errors") {
      messages.push(...errors)
    } else {
      fieldErrors[key] = errors
      messages.push(`${key}: ${errors.join(", ")}`)
    }
  }

  return {
    message: messages.join("; ") || "Validation error",
    fieldErrors,
  }
}

export const safeFetch = async <T = unknown>(
  url: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> => {
  const controller = new AbortController()
  const timeout = setTimeout(
    () => controller.abort(),
    CONFIG.FETCH_TIMEOUT_MS,
  )

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    })

    const contentType = response.headers.get("content-type") ?? ""
    const retryHeader = Number(response.headers.get("retry-after"))
    const retryAfter =
      response.status === 429
        ? Number.isFinite(retryHeader) && retryHeader > 0 ? Math.ceil(retryHeader) : 1
        : undefined

    if (contentType.includes("text/html")) {
      const html = await response.text()
      const extracted = extractHtmlMessage(html)
      return {
        ok: false,
        error: {
          message: `Server Error (${response.status}): ${extracted}`,
          status: response.status,
          isHtml: true,
          retryAfter,
        },
      }
    }

    if (contentType.includes("application/json")) {
      const json = await response.json()

      if (response.ok) {
        return { ok: true, data: json as T }
      }

      const { message, fieldErrors } = formatDrfErrors(
        json as Record<string, unknown>,
      )
      return {
        ok: false,
        error: {
          message,
          fieldErrors,
          status: response.status,
          isHtml: false,
          retryAfter,
        },
      }
    }

    const text = await response.text()
    if (!response.ok) {
      return {
        ok: false,
        error: {
          message: `Error (${response.status}): ${text.slice(0, 200)}`,
          status: response.status,
          isHtml: false,
          retryAfter,
        },
      }
    }

    return { ok: true, data: text as unknown as T }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return {
        ok: false,
        error: {
          message: "The server took too long to answer. Try again in a moment.",
          status: 0,
          isHtml: false,
        },
      }
    }

    return {
      ok: false,
      error: {
        message: navigator.onLine === false
          ? "You are offline. Check your connection and try again."
          : "Can't reach the server. Check your connection and try again.",
        status: 0,
        isHtml: false,
      },
    }
  } finally {
    clearTimeout(timeout)
  }
}

export const safeParseJson = (
  raw: string,
): { ok: true; data: unknown } | { ok: false; error: string } => {
  try {
    return { ok: true, data: JSON.parse(raw) }
  } catch {
    return { ok: false, error: `Failed to parse JSON: ${raw.slice(0, 100)}` }
  }
}
