export type WsClientMessage =
  | { action: "start_battle_request" }
  | {
      action: "submit_code";
      language: string;
      code: string;
      task_id: number;
    };

export type WsServerEvent =
  | { event: "user_joined"; data: { user_id: number; username: string } }
  | { event: "user_left"; data: { user_id: number; username: string } }
  | {
      event: "lobby_update";
      data: { participants_count: number; task_id?: number };
    }
  | { event: "battle_started"; data: { deadline: number } }
  | {
      event: "opponent_running_code";
      data: { user_id: number; username: string };
    }
  | {
      event: "execution_result";
      data: {
        status: string;
        is_correct: boolean;
        message: string;
        details?: string;
      };
    }
  | {
      event: "battle_finished";
      data: {
        winner_id: number | null;
        winner_username: string | null;
        reason: "solved" | "time_up";
      };
    }
  | { event: "error"; data: { message: string } };
