"""A small stand-in for Django's internal API (the contract in backend/apps/battles/views/*).
Plugged in as the httpx transport of services.django_callbacks, so the real client code runs."""

import json
import re
import time

import httpx

TASK = {
    "id": 1,
    "name": "echo",
    "description": "print the number",
    "difficulty": 1,
    "time_limit": {"seconds": 1, "nanos": 0},
    "memory_limit_bytes": 256 * 1024 * 1024,
    "public_tests": {"input": ["1\n"], "output": ["1"]},
    "private_tests": {"input": ["PRIVATE-IN-555\n"], "output": ["PRIVATE-OUT-666"]},
    "generated_tests": {"input": ["HIDDEN-IN-777\n"], "output": ["HIDDEN-OUT-888"]},
}


FACETS = {
    "total": 3, "difficulties": [{"value": "easy", "count": 3}], "sources": [],
    "tags": [{"value": "math", "count": 3}], "rating": {"min": 800, "max": 800}, "orderings": ["id"],
}  # fmt: skip


class FakeDjango:
    def __init__(self):
        self.battles: dict[int, dict] = {}
        self.left: list[tuple[int, int]] = []
        self.finishes: list[tuple[int, int | None]] = []
        self.task_requests: list[int] = []
        self.catalog_queries: list[dict] = []
        self.catalog_count = 3
        self.joins: list[dict] = []
        self.down = False  # connection refused
        self.finish_status = 200  # what finish answers (503 simulates a Django outage)
        self.ready_status = 200

    def add_battle(self, battle_id, creator, *, type="1v1", max_participants=2, task=1,
                   invite=None, status="pending", duration_seconds=60):
        self.battles[battle_id] = {
            "creator": creator, "type": type, "max": max_participants, "task": task,
            "invite": invite, "status": status, "duration": duration_seconds, "parts": {},
        }

    def players(self, battle) -> int:
        return sum(1 for role in battle["parts"].values() if role == "player")

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("django is down", request=request)
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(403, json={"detail": "no token"})
        path = request.url.path
        body = json.loads(request.content) if request.content else {}

        if path == "/ready":
            return httpx.Response(self.ready_status, json={"status": "ok"})
        if match := re.fullmatch(r"/internal/tasks/(\d+)/", path):
            self.task_requests.append(int(match.group(1)))
            return httpx.Response(200, json=TASK)
        if path == "/internal/tasks/facets/":
            return httpx.Response(200, json=FACETS)
        if path == "/internal/tasks/":
            self.catalog_queries.append(dict(request.url.params))
            limit = int(request.url.params["limit"])
            offset = int(request.url.params["offset"])
            item = {k: TASK[k] for k in ("id", "name", "difficulty", "time_limit", "memory_limit_bytes")}
            item.update(difficulty_label="easy", cf_rating=800, internal="x")
            count = self.catalog_count
            return httpx.Response(200, json={"count": count, "next": None, "previous": None,
                                             "results": [item] * max(0, min(limit, count - offset))})

        match = re.fullmatch(r"/internal/battles/(join|leave|start|finish|delete)/(\d+)/", path)
        if not match:
            return httpx.Response(404, json={"detail": "Not found."})
        action, battle_id = match.group(1), int(match.group(2))
        battle = self.battles.get(battle_id)
        if action == "finish" and self.finish_status != 200:
            return httpx.Response(self.finish_status, text="<html>" + "x" * 2000 + "</html>")
        if action == "finish" and battle is None:  # tests finish battles they never created
            self.finishes.append((battle_id, body["winner_id"]))
            return httpx.Response(200, json={"status": "success"})
        if battle is None:
            return httpx.Response(404, json={"detail": "Not found."})

        user_id = body.get("user_id")
        if action == "join":
            return self._join(battle, battle_id, body)
        if action == "leave":
            self.left.append((battle_id, user_id))
            if battle["status"] == "pending":
                battle["parts"].pop(user_id, None)
            return httpx.Response(200, json={"battle_status": battle["status"],
                                             "players_count": self.players(battle)})
        if action == "start":
            if user_id != battle["creator"]:
                return httpx.Response(403, json={"detail": "Only the creator can start the battle."})
            if battle["status"] != "pending" or self.players(battle) < 2:
                return httpx.Response(409, json={"detail": "Cannot start: not pending or too few players."})
            battle["status"] = "active"
            return httpx.Response(200, json={"status": "success",
                                             "deadline": time.time() + battle["duration"]})
        if action == "finish":
            battle["status"] = "finished"
            self.finishes.append((battle_id, body["winner_id"]))
            return httpx.Response(200, json={"status": "success"})
        return httpx.Response(204)

    def _join(self, battle, battle_id, body):
        user_id, role = body["user_id"], body.get("role")
        self.joins.append({"battle": battle_id, **body})
        if battle["status"] == "finished":
            return httpx.Response(409, json={"detail": "Battle is finished."})
        if user_id not in battle["parts"]:
            if battle["invite"] and user_id != battle["creator"] and body.get("invite_code") != battle["invite"]:
                return httpx.Response(403, json={"detail": "This battle is private."})
            pending = battle["status"] == "pending"
            has_room = pending and self.players(battle) < battle["max"]
            if role == "player" and not has_room:
                return httpx.Response(409, json={"detail": "Battle is full." if pending else "Battle has already started."})
            battle["parts"][user_id] = role or ("player" if has_room else "spectator")
        return httpx.Response(200, json={
            "id": 1, "role": battle["parts"][user_id], "status": "waiting",
            "battle_status": battle["status"], "type": battle["type"],
            "max_participants": battle["max"], "players_count": self.players(battle),
            "task_id": battle["task"], "creator_id": battle["creator"],
            "creator_username": f"user{battle['creator']}", "duration": battle["duration"] / 60,
        })
