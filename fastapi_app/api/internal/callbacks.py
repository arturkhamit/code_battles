from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class SyncRequest(BaseModel):
    action: str


@router.post("/internal/battles/{battle_id}/sync")
async def sync_battle_state(battle_id: int, data: SyncRequest):
    return {"status": "synced"}
