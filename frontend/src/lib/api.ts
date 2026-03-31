import { CONFIG } from "../config"

export type ApiError = {
  message: string
  fieldErrors?: Record<string, string[]>
  status: number
  isHtml: boolean
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

    if (contentType.includes("text/html")) {
      const html = await response.text()
      const extracted = extractHtmlMessage(html)
      return {
        ok: false,
        error: {
          message: `Server Error (${response.status}): ${extracted}`,
          status: response.status,
          isHtml: true,
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
        error: { message, fieldErrors, status: response.status, isHtml: false },
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
        },
      }
    }

    return { ok: true, data: text as unknown as T }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      return {
        ok: false,
        error: {
          message: "Request timed out. The server did not respond in time.",
          status: 0,
          isHtml: false,
        },
      }
    }

    return {
      ok: false,
      error: {
        message:
          err instanceof Error
            ? `Network error: ${err.message}`
            : "An unexpected network error occurred",
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
