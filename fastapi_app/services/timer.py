import asyncio


async def battle_timer(battle_id: int, duration_seconds: int, callback):
    await asyncio.sleep(duration_seconds)
    await callback(battle_id)
