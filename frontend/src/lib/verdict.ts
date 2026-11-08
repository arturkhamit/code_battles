import type { SubmitStatus } from "../types/battle"
import type { ExecutionResult } from "../types/ws"

const TITLES: Record<string, string> = {
  accepted: "Accepted",
  wrong_answer: "Wrong answer",
  time_limit: "Time limit exceeded",
  runtime_error: "Runtime error",
  memory_limit: "Memory limit exceeded",
  compile_error: "Compilation error",
  error: "Judge error",
}

/** execution_result -> what the verdict panel says: "Wrong answer on hidden test #4" + details. */
export const verdictStatus = (r: ExecutionResult): SubmitStatus => {
  const title = TITLES[r.verdict] ?? (r.is_correct ? "Accepted" : r.message || "Rejected")
  const where =
    r.test_number && r.verdict !== "compile_error"
      ? ` on ${r.hidden ? "hidden " : ""}test #${r.test_number}`
      : ""
  const stats = [
    r.total ? `${r.passed ?? 0} of ${r.total} tests passed` : null,
    r.time_ms != null ? `${r.time_ms} ms` : null,
    r.memory_mb != null ? `${r.memory_mb} MB` : null,
  ]
    .filter(Boolean)
    .join(" · ")
  if (r.is_correct) return { kind: "accepted", message: title, detail: stats || undefined }
  return { kind: "wrong", message: `${title}${where}`, stats: stats || undefined, detail: r.details || undefined }
}
