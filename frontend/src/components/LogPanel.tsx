import { useEffect, useRef } from "react";
import type { LogEntry } from "../types/battle";

type LogPanelProps = {
  logs: LogEntry[];
};

const logLevelClass: Record<LogEntry["level"], string> = {
  info: "text-ctp-subtext1",
  success: "text-ctp-green",
  error: "text-ctp-red",
  system: "text-ctp-yellow",
};

export const LogPanel = ({ logs }: LogPanelProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <section
      className="flex flex-[0.8] flex-col overflow-hidden rounded-xl bg-ctp-surface0 p-4 shadow-lg"
      aria-label="Broadcast log"
    >
      <h3 className="mb-2 text-sm font-semibold">Broadcasting</h3>
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto rounded bg-ctp-crust p-2 font-mono text-xs"
        role="log"
        aria-live="polite"
      >
        {logs.map((entry, i) => (
          <div
            key={i}
            className={`${logLevelClass[entry.level]} whitespace-pre-wrap`}
          >
            [{entry.timestamp}] {entry.message}
          </div>
        ))}
      </div>
    </section>
  );
};
