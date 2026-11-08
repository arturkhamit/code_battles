import { useEffect, useRef, useState } from "react"
import { fetchTaskInfo } from "../../lib/tasks"
import { btn } from "../../lib/ui"
import type { TaskInfo, TaskListItem } from "../../types/task"
import { TaskPanel } from "../TaskPanel"
import { Icon } from "../ui/Icon"
import { TaskCatalog } from "./TaskCatalog"

type Props = {
  open: boolean
  initialId: number | null
  onClose: () => void
  onPick: (id: number) => void
}

/** The catalog in a modal: browse on the left, read the statement on the right, pick. */
export const TaskPickerDialog = ({ open, initialId, onClose, onPick }: Props) => {
  const ref = useRef<HTMLDialogElement>(null)
  const [previewId, setPreviewId] = useState<number | null>(initialId)
  const [picked, setPicked] = useState<TaskListItem | null>(null)
  const [info, setInfo] = useState<{ id: number; task: TaskInfo | null; error: string | null } | null>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  useEffect(() => {
    if (!open || previewId === null) return
    let cancelled = false
    fetchTaskInfo(previewId).then((r) => {
      if (!cancelled) setInfo({ id: previewId, task: r.ok ? r.data : null, error: r.ok ? null : r.error.message })
    })
    return () => {
      cancelled = true
    }
  }, [open, previewId])

  const current = info?.id === previewId ? info : null
  const item = picked?.id === previewId ? picked : null

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="picker-title"
      className="m-auto h-dvh max-h-dvh w-full max-w-none overflow-hidden overscroll-contain bg-bg p-0 text-text sm:h-[min(52rem,92dvh)] sm:w-[min(72rem,94vw)] sm:rounded-xl sm:border sm:border-card-border"
    >
      {open && (
        <div className="flex h-full flex-col">
          <header className="flex items-center justify-between gap-3 border-b border-card-border px-4 py-3 pt-[max(0.75rem,env(safe-area-inset-top))]">
            <h2 id="picker-title" className="font-mono text-lg font-bold">
              Choose a task
            </h2>
            <button type="button" onClick={onClose} className={`${btn.ghost} px-2`} aria-label="Close">
              <Icon name="x" className="h-5 w-5" />
            </button>
          </header>
          <div className="grid min-h-0 flex-1 grid-cols-1 md:grid-cols-[minmax(18rem,24rem)_1fr]">
            <div className={`flex min-h-0 flex-col p-4 md:border-r md:border-card-border ${previewId !== null ? "max-md:hidden" : ""}`}>
              <TaskCatalog
                selectedId={previewId}
                onSelect={(id, task) => {
                  setPreviewId(id)
                  setPicked(task)
                }}
              />
            </div>
            <div className={`flex min-h-0 flex-col gap-3 p-4 ${previewId === null ? "max-md:hidden" : ""}`}>
              <button type="button" onClick={() => setPreviewId(null)} className={`${btn.ghost} -ml-2 self-start px-2 md:hidden`}>
                <Icon name="back" />
                All tasks
              </button>
              {previewId === null ? (
                <p className="text-sm text-sub">Choose a task to read its statement.</p>
              ) : (
                <TaskPanel
                  task={current?.task ?? null}
                  item={item}
                  phase="active"
                  error={current?.error}
                  actions={
                    current?.task && (
                      <button type="button" onClick={() => onPick(previewId)} className={btn.primary}>
                        Pick for battle
                      </button>
                    )
                  }
                />
              )}
            </div>
          </div>
        </div>
      )}
    </dialog>
  )
}
