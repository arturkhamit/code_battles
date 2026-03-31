from typing import List

from pydantic import BaseModel


class BattleCreatedEvent(BaseModel):
    battle_id: int
    participants: List[int]


class BattleStartedEvent(BaseModel):
    battle_id: int
