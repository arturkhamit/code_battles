import { useCallback, useMemo, useReducer, useRef } from "react";
import { CONFIG } from "../config";
import { safeFetch } from "../lib/api";
import type {
  ApiErrorState,
  BattlePhase,
  BattleState,
  BattleType,
  Language,
  LogEntry,
  SubmitStatus,
} from "../types/battle";
import type { TaskInfo } from "../types/task";
import type { WsServerEvent } from "../types/ws";
import { useTimer } from "./use-timer";
import { useWebSocket } from "./use-websocket";

type Action =
  | { type: "SET_PHASE"; phase: BattlePhase }
  | { type: "SET_BATTLE_ID"; battleId: number | null }
  | { type: "SET_TASK_ID"; taskId: number }
  | { type: "SET_BATTLE_TYPE"; battleType: BattleType }
  | { type: "SET_DURATION"; duration: number }
  | { type: "SET_DEADLINE"; deadline: number | null }
  | { type: "SET_PARTICIPANTS"; count: number }
  | { type: "SET_SUBMIT_STATUS"; status: SubmitStatus }
  | { type: "ADD_LOG"; entry: LogEntry }
  | { type: "SET_ERROR"; error: ApiErrorState | null }
  | { type: "RESET" };

const initialState: BattleState = {
  phase: "idle",
  battleId: null,
  taskId: 1,
  battleType: "1v1",
  duration: 15,
  deadline: null,
  participantsCount: 0,
  submitStatus: { kind: "none" },
  logs: [
    {
      timestamp: new Date().toLocaleTimeString(),
      message: "System is ready...",
      level: "system",
    },
  ],
  error: null,
};

const reducer = (state: BattleState, action: Action): BattleState => {
  switch (action.type) {
    case "SET_PHASE":
      return { ...state, phase: action.phase };
    case "SET_BATTLE_ID":
      return { ...state, battleId: action.battleId };
    case "SET_TASK_ID":
      return { ...state, taskId: action.taskId };
    case "SET_BATTLE_TYPE":
      return { ...state, battleType: action.battleType };
    case "SET_DURATION":
      return { ...state, duration: action.duration };
    case "SET_DEADLINE":
      return { ...state, deadline: action.deadline };
    case "SET_PARTICIPANTS":
      return { ...state, participantsCount: action.count };
    case "SET_SUBMIT_STATUS":
      return { ...state, submitStatus: action.status };
    case "ADD_LOG":
      return { ...state, logs: [...state.logs, action.entry] };
    case "SET_ERROR":
      return { ...state, error: action.error };
    case "RESET":
      return {
        ...initialState,
        taskId: state.taskId,
        battleType: state.battleType,
        duration: state.duration,
        logs: state.logs,
      };
    default:
      return state;
  }
};

export const useBattle = (userId: number, username: string) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [taskInfo, setTaskInfo] = useReducer(
    (_: TaskInfo | null, next: TaskInfo | null) => next,
    null,
  );

  const phaseRef = useRef(state.phase);
  phaseRef.current = state.phase;

  const timer = useTimer();

  const addLog = useCallback(
    (message: string, level: LogEntry["level"] = "info") => {
      dispatch({
        type: "ADD_LOG",
        entry: { timestamp: new Date().toLocaleTimeString(), message, level },
      });
    },
    [],
  );

  const handleWsEvent = useCallback(
    (event: WsServerEvent) => {
      switch (event.event) {
        case "lobby_update": {
          dispatch({
            type: "SET_PARTICIPANTS",
            count: event.data.participants_count,
          });
          break;
        }
        case "battle_started": {
          addLog("Battle STARTED! Good luck!", "success");
          dispatch({ type: "SET_PHASE", phase: "active" });
          dispatch({ type: "SET_DEADLINE", deadline: event.data.deadline });
          timer.start(event.data.deadline);
          break;
        }
        case "battle_finished": {
          timer.stop();
          dispatch({ type: "SET_PHASE", phase: "finished" });

          if (event.data.reason === "time_up") {
            addLog("Time is up! No winner.", "error");
            dispatch({
              type: "SET_SUBMIT_STATUS",
              status: { kind: "error", message: "TIME IS UP! NO WINNER." },
            });
          } else {
            addLog(
              `Battle finished! Winner: User ${event.data.winner_username}:${event.data.winner_id}`,
              "success",
            );
            dispatch({
              type: "SET_SUBMIT_STATUS",
              status: { kind: "accepted", message: "BATTLE FINISHED!" },
            });
          }
          break;
        }
        case "execution_result": {
          if (event.data.is_correct) {
            dispatch({
              type: "SET_SUBMIT_STATUS",
              status: {
                kind: "accepted",
                message: "ACCEPTED (All test cases passed)",
              },
            });
            addLog("All test cases passed!", "success");
          } else {
            dispatch({
              type: "SET_SUBMIT_STATUS",
              status: { kind: "wrong", message: event.data.message },
            });
            addLog(
              `Tests failed: ${event.data.message}\n${event.data.details}`,
              "error",
            );
          }
          break;
        }
        case "opponent_running_code": {
          addLog(
            `User ${event.data.username}:${event.data.user_id} is running code...`,
            "system",
          );
          break;
        }
        case "user_joined": {
          addLog(
            `User ${event.data.username}:${event.data.user_id} joined!`,
            "system",
          );
          break;
        }
        case "user_left": {
          addLog(
            `User ${event.data.username}:${event.data.user_id} left.`,
            "error",
          );
          break;
        }
        case "error": {
          addLog(`Server error: ${event.data.message}`, "error");
          dispatch({
            type: "SET_ERROR",
            error: { message: event.data.message },
          });
          break;
        }
        default: {
          addLog(
            `Unknown event: ${(event as { event: string }).event}`,
            "system",
          );
        }
      }
    },
    [addLog, timer],
  );

  const ws = useWebSocket({
    onEvent: handleWsEvent,
    onOpen: () => {
      addLog("Connected! Waiting in lobby...", "success");
    },
    onClose: (wasClean) => {
      if (wasClean || phaseRef.current === "finished") {
        addLog("Connection closed.", "info");
      } else {
        addLog("Connection lost unexpectedly.", "error");
      }
      if (phaseRef.current !== "active" && phaseRef.current !== "finished") {
        dispatch({ type: "SET_PHASE", phase: "idle" });
      }
    },
    onError: (message) => {
      addLog(message, "error");
    },
    shouldReconnect: () => phaseRef.current === "active",
  });

  const fetchTask = useCallback(
    async (taskId: number) => {
      const result = await safeFetch<TaskInfo>(
        `${CONFIG.FASTAPI_URL}/api/tasks/${taskId}/info`,
      );
      if (result.ok) {
        setTaskInfo(result.data);
      } else {
        addLog(`Failed to load task: ${result.error.message}`, "error");
        setTaskInfo(null);
      }
    },
    [addLog],
  );

  const handleCreate = useCallback(async () => {
    dispatch({ type: "SET_ERROR", error: null });

    ws.disconnect();
    dispatch({ type: "RESET" });
    dispatch({ type: "SET_ERROR", error: null });

    const errors: Record<string, string[]> = {};
    if (!state.taskId || state.taskId <= 0) {
      errors.task = ["Task ID must be a positive number"];
    }
    if (!state.duration || state.duration <= 0) {
      errors.duration = ["Duration must be a positive number"];
    }

    if (Object.keys(errors).length > 0) {
      dispatch({
        type: "SET_ERROR",
        error: {
          message: Object.values(errors).flat().join("; "),
          fieldErrors: errors,
        },
      });
      return;
    }

    dispatch({ type: "SET_PHASE", phase: "creating" });
    addLog("Requesting server to create a new battle...", "system");

    const payload = {
      task: state.taskId,
      creator: userId,
      type: state.battleType,
      ranked: false,
      duration: state.duration,
    };

    const result = await safeFetch<{ id?: number; battle_id?: number }>(
      `${CONFIG.DJANGO_URL}/api/internal/battles/create/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );

    if (!result.ok) {
      dispatch({ type: "SET_PHASE", phase: "idle" });
      dispatch({ type: "SET_ERROR", error: result.error });
      addLog(`Failed to create battle: ${result.error.message}`, "error");
      return;
    }

    const battleId = result.data.id ?? result.data.battle_id;
    if (!battleId) {
      dispatch({ type: "SET_PHASE", phase: "idle" });
      dispatch({
        type: "SET_ERROR",
        error: {
          message: "Server returned success but no battle ID",
          status: 200,
          isHtml: false,
        },
      });
      return;
    }

    addLog(`Battle created! ID: ${battleId}`, "success");
    dispatch({ type: "SET_BATTLE_ID", battleId });
    dispatch({ type: "SET_PHASE", phase: "lobby" });

    ws.connect(battleId, userId, username);
    fetchTask(state.taskId);
  }, [
    userId,
    username,
    state.taskId,
    state.duration,
    state.battleType,
    addLog,
    ws,
    fetchTask,
  ]);

  const handleJoin = useCallback(() => {
    dispatch({ type: "SET_ERROR", error: null });

    const errors: Record<string, string[]> = {};
    if (!state.battleId || state.battleId <= 0) {
      errors.battle_id = ["Please enter a valid Battle ID"];
    }

    if (Object.keys(errors).length > 0) {
      dispatch({
        type: "SET_ERROR",
        error: {
          message: Object.values(errors).flat().join("; "),
          fieldErrors: errors,
        },
      });
      return;
    }

    dispatch({ type: "SET_PHASE", phase: "lobby" });
    addLog(`Joining battle ${state.battleId}...`, "system");
    ws.connect(state.battleId!, userId, username);
    fetchTask(state.taskId);
  }, [state.battleId, userId, username, state.taskId, addLog, ws, fetchTask]);

  const handleStartBattle = useCallback(() => {
    if (phaseRef.current !== "lobby") return;
    addLog("Requesting server to start the battle...", "system");
    ws.send({ action: "start_battle_request" });
  }, [addLog, ws]);

  const handleSubmitCode = useCallback(
    (code: string, language: Language) => {
      if (phaseRef.current !== "active") return;
      dispatch({ type: "SET_SUBMIT_STATUS", status: { kind: "running" } });
      addLog("Code submitted...", "system");
      ws.send({
        action: "submit_code",
        language,
        code,
        task_id: state.taskId,
      });
    },
    [addLog, ws, state.taskId],
  );

  const handleDisconnect = useCallback(() => {
    ws.disconnect();
    timer.reset();
    dispatch({ type: "RESET" });
    addLog("Disconnected.", "info");
  }, [ws, timer, addLog]);

  const clearError = useCallback(() => {
    dispatch({ type: "SET_ERROR", error: null });
  }, []);

  const canShowStartButton = useMemo(
    () =>
      state.phase === "lobby" &&
      state.battleType === "1v1" &&
      state.participantsCount >= 1,
    [state.phase, state.battleType, state.participantsCount],
  );

  return {
    state,
    taskInfo,
    timer,
    canShowStartButton,
    dispatch,
    handleCreate,
    handleJoin,
    handleStartBattle,
    handleSubmitCode,
    handleDisconnect,
    clearError,
  };
};
