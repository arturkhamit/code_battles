from typing import Dict

from fastapi import WebSocket


class BattleConnectionManager:
    def __init__(self):
        self.active_battles: Dict[int, Dict[int, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, battle_id: int, user_id: int):
        try:
            await websocket.accept()
            if battle_id not in self.active_battles:
                self.active_battles[battle_id] = {}
            self.active_battles[battle_id][user_id] = websocket
        except Exception as e:
            print(f"Error while connecting (User {user_id}): {e}")

    def disconnect(self, battle_id: int, user_id: int):
        try:
            if (
                battle_id in self.active_battles
                and user_id in self.active_battles[battle_id]
            ):
                del self.active_battles[battle_id][user_id]

                if not self.active_battles[battle_id]:
                    del self.active_battles[battle_id]
        except Exception as e:
            print(f"Error while disconnecting (User {user_id}): {e}")

    async def broadcast(self, battle_id: int, message: dict):
        if battle_id in self.active_battles:
            for connection in list(self.active_battles[battle_id].values()):
                try:
                    await connection.send_json(message)
                except RuntimeError:
                    pass
                except Exception as e:
                    print(f"Unexpected error while broadcasting: {e}")

    async def send_personal(self, battle_id: int, user_id: int, message: dict):
        if (
            battle_id in self.active_battles
            and user_id in self.active_battles[battle_id]
        ):
            ws = self.active_battles[battle_id][user_id]
            try:
                await ws.send_json(message)
            except RuntimeError:
                pass
            except Exception as e:
                print(f"Unexpected error while send_personal() (User {user_id}): {e}")


manager = BattleConnectionManager()
