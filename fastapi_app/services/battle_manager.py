from fastapi import WebSocket


class BattleConnectionManager:
    def __init__(self):
        # { battle_id: [ {"user_id": 1, "ws": WebSocket}, {"user_id": 2, "ws": WebSocket} ] }
        self.active_battles: dict[int, list[dict]] = {}

    async def connect(self, websocket: WebSocket, battle_id: int, user_id: int):
        await websocket.accept()
        if battle_id not in self.active_battles:
            self.active_battles[battle_id] = []

        self.active_battles[battle_id].append({"user_id": user_id, "ws": websocket})

        await self.broadcast(
            battle_id,
            {"type": "system", "message": f"User {user_id} joined the battle!"},
        )

    def disconnect(self, websocket: WebSocket, battle_id: int, user_id: int):
        if battle_id in self.active_battles:
            self.active_battles[battle_id] = [
                conn
                for conn in self.active_battles[battle_id]
                if conn["ws"] != websocket
            ]
            if not self.active_battles[battle_id]:
                del self.active_battles[battle_id]

    async def broadcast(self, battle_id: int, message: dict):
        if battle_id in self.active_battles:
            for connection in self.active_battles[battle_id]:
                try:
                    await connection["ws"].send_json(message)
                except Exception:
                    pass

    async def close_battle(self, battle_id: int):
        if battle_id in self.active_battles:
            for connection in self.active_battles[battle_id]:
                try:
                    await connection["ws"].close()
                except Exception:
                    pass
            del self.active_battles[battle_id]


manager = BattleConnectionManager()
