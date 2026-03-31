import type { BattlePhase } from "../types/battle"
import type { TaskInfo } from "../types/task"

type TaskPanelProps = {
  task: TaskInfo | null
  phase: BattlePhase
}

export const TaskPanel = ({ task, phase }: TaskPanelProps) => {
  if (!task) {
    const message =
      phase === "idle"
        ? "Connect to a battle to see a task"
        : "Loading task..."

    return (
      <section
        className="flex flex-1 flex-col overflow-y-auto rounded-xl bg-ctp-surface0 p-4 shadow-lg"
        aria-label="Task panel"
      >
        <h2 className="text-lg font-semibold text-ctp-yellow">
          Waiting for a connection...
        </h2>
        <p className="mt-2 text-sm text-ctp-subtext0">{message}</p>
      </section>
    )
  }

  const inputs = task.public_tests?.input ?? []
  const outputs = task.public_tests?.output ?? []

  return (
    <section
      className="flex flex-1 flex-col overflow-y-auto rounded-xl bg-ctp-surface0 p-4 shadow-lg"
      aria-label="Task panel"
    >
      <h2 className="text-lg font-semibold text-ctp-yellow">{task.name}</h2>
      <p className="mt-2 whitespace-pre-wrap text-sm">{task.description}</p>
      {task.time_limit && (
        <p className="mt-2 text-xs text-ctp-subtext1">
          Time limit: {task.time_limit} sec.
        </p>
      )}

      {inputs.length > 0 && (
        <div className="mt-4">
          <h3 className="mb-2 text-sm font-semibold">Examples:</h3>
          {inputs.map((input, i) => (
            <div
              key={i}
              className="mb-2 rounded border-l-[3px] border-ctp-blue bg-ctp-crust p-3"
            >
              <div className="text-xs font-semibold">Input:</div>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-sm text-ctp-green">
                {input}
              </pre>
              {outputs[i] !== undefined && (
                <>
                  <div className="mt-2 text-xs font-semibold">
                    Expected Output:
                  </div>
                  <pre className="mt-1 whitespace-pre-wrap font-mono text-sm text-ctp-green">
                    {outputs[i]}
                  </pre>
                </>
              )}
            </div>
          ))}
        </div>
      )}
      {inputs.length === 0 && (
        <p className="mt-4 text-xs text-ctp-subtext0">No public tests</p>
      )}
    </section>
  )
}
