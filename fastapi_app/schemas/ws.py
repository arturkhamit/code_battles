"""Messages a client may send over /ws/battle/{id}. The union is discriminated by `action`
(frontend/src/types/ws.ts: WsClientMessage). Unknown extra keys are ignored on purpose: the old
client still sends `task_id` with submit_code, and the server must never use it."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

MAX_FRAME_BYTES = 128 * 1024
MAX_CODE_CHARS = 64 * 1024
MAX_CHAT_CHARS = 1000


class StartBattle(BaseModel):
    action: Literal["start_battle_request"]


class SubmitCode(BaseModel):
    action: Literal["submit_code"]
    language: str = Field(min_length=1, max_length=32)
    code: str = Field(max_length=MAX_CODE_CHARS)


class SendChat(BaseModel):
    action: Literal["send_chat"]
    message: str = Field(max_length=MAX_CHAT_CHARS)


class RoleAssigned(BaseModel):
    """Data of the server event `role_assigned`, taken from Django's join answer: the first
    thing a socket gets, so it never depends on a lobby_update published before it registered
    (frontend/src/types/ws.ts: WsRoleAssigned)."""

    role: Literal["player", "spectator"]
    battle_id: int
    task_id: int | None
    type: str
    battle_status: str
    players_count: int
    max_participants: int
    creator_id: int
    is_creator: bool
    # for the lobby header; optional so an older Django answer still validates
    creator_username: str | None = None
    duration: float | None = None  # minutes


ClientMessage = Annotated[StartBattle | SubmitCode | SendChat, Field(discriminator="action")]
client_message = TypeAdapter(ClientMessage)
