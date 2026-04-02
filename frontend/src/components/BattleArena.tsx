import { CodePanel } from "./CodePanel";
import { Controls } from "./Controls";
import { ErrorBanner } from "./ErrorBanner";
import { Header } from "./Header";
import { LogPanel } from "./LogPanel";
import { TaskPanel } from "./TaskPanel";
import { useBattle } from "../hooks/use-battle";
import type { BattleType } from "../types/battle";

type BattleArenaProps = {
  userId: number;
  username: string;
  onLogout: () => void;
};

export const BattleArena = ({
  userId,
  username,
  onLogout,
}: BattleArenaProps) => {
  const battle = useBattle(userId, username);
  const { state, taskInfo, timer, canShowStartButton, dispatch } = battle;

  return (
    <div className="flex h-screen flex-col gap-3 p-5">
      <Header timerLabel={timer.label} phase={state.phase} />

      <Controls
        phase={state.phase}
        username={username}
        taskId={state.taskId}
        battleType={state.battleType}
        duration={state.duration}
        battleId={state.battleId}
        canShowStart={canShowStartButton}
        fieldErrors={state.error?.fieldErrors}
        onTaskIdChange={(v) => dispatch({ type: "SET_TASK_ID", taskId: v })}
        onBattleTypeChange={(v: BattleType) =>
          dispatch({ type: "SET_BATTLE_TYPE", battleType: v })
        }
        onDurationChange={(v) =>
          dispatch({ type: "SET_DURATION", duration: v })
        }
        onBattleIdChange={(v) =>
          dispatch({ type: "SET_BATTLE_ID", battleId: v || null })
        }
        onCreate={battle.handleCreate}
        onJoin={battle.handleJoin}
        onStart={battle.handleStartBattle}
        onDisconnect={battle.handleDisconnect}
        onLogout={onLogout}
      />

      {state.error && (
        <ErrorBanner error={state.error} onDismiss={battle.clearError} />
      )}

      <div className="flex min-h-0 flex-1 gap-3">
        <TaskPanel task={taskInfo} phase={state.phase} />
        <CodePanel
          phase={state.phase}
          submitStatus={state.submitStatus}
          onSubmit={battle.handleSubmitCode}
        />
        <LogPanel logs={state.logs} />
      </div>
    </div>
  );
};
