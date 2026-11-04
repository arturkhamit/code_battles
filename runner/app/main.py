"""Code Battles sandbox runner.

  POST /run    {language, code, tests: {public, hidden}, time_limit_ms, memory_limit_mb} -> verdict
               Authorization: Bearer RUNNER_TOKEN
  GET  /health liveness: 200 while the process answers
  GET  /ready  Docker answers and both sandbox images are present (503 otherwise)

Listens on the internal network only; Docker is reached through the socket proxy
(SANDBOX_DOCKER_URL), never the socket.
"""

import asyncio
import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings
from app.executor import Sandbox, SandboxError, make_client
from app.logging_config import setup_logging
from app.reaper import reaper_loop
from app.schemas import MAX_BODY_BYTES, RunRequest
from app.verdict import build_response

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, sandbox: Sandbox | None = None) -> FastAPI:
    """`sandbox` is for tests: with it the app never touches Docker (and starts no reaper)."""
    settings = settings or Settings()
    setup_logging(settings.LOG_LEVEL)
    slots = asyncio.Semaphore(settings.RUNNER_MAX_CONCURRENCY)
    token = settings.RUNNER_TOKEN.encode()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        reaper = None
        if sandbox is None:
            client = make_client(settings)
            app.state.sandbox = Sandbox(client, settings)
            reaper = asyncio.create_task(reaper_loop(client), name="reaper")
        yield
        if reaper is not None:
            reaper.cancel()
            await asyncio.gather(reaper, return_exceptions=True)
            app.state.sandbox.client.close()

    app = FastAPI(title="Code Battles runner", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.sandbox = sandbox
    app.state.active = 0

    @app.middleware("http")
    async def guard_run(request: Request, call_next):
        """Before the body is read: the right token, and not a body of a few hundred megabytes."""
        if request.url.path == "/run":
            given = request.headers.get("authorization", "")
            scheme, _, value = given.partition(" ")
            if scheme.lower() != "bearer" or not hmac.compare_digest(value.encode(), token):
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            length = request.headers.get("content-length")
            if length is None or not length.isdigit() or int(length) > MAX_BODY_BYTES:
                return JSONResponse({"error": "body too large or without Content-Length"}, status_code=413)
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # the default answer echoes the whole input back: megabytes of tests
        problems = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()[:10]]
        return JSONResponse({"error": "invalid_request", "detail": problems}, status_code=422)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        checks = await asyncio.to_thread(app.state.sandbox.check)
        ok = all(state == "ok" for state in checks.values())
        return JSONResponse(
            {"status": "ok" if ok else "unavailable", "checks": checks, "active": app.state.active},
            status_code=200 if ok else 503,
        )

    @app.post("/run")
    async def run(body: RunRequest):
        try:
            await asyncio.wait_for(slots.acquire(), settings.RUNNER_QUEUE_TIMEOUT_SECONDS)
        except TimeoutError:
            return JSONResponse({"error": "busy"}, status_code=503, headers={"Retry-After": "2"})
        app.state.active += 1
        started = time.monotonic()

        async def judged():
            # The slot belongs to the worker thread, not to the request: if the client goes away
            # (handler cancelled), the container lives until judge() returns.
            try:
                return await asyncio.to_thread(app.state.sandbox.judge, body)
            finally:
                app.state.active -= 1
                slots.release()

        try:
            answer = await asyncio.shield(asyncio.ensure_future(judged()))
            response = build_response(answer, body)
        except SandboxError as exc:
            logger.error("Sandbox failure: %s", exc)
            return JSONResponse({"error": "sandbox_unavailable"}, status_code=503)
        logger.info(
            "Judged", extra={
                "language": body.language, "verdict": response["verdict"], "passed": response["passed"],
                "total": response["total"], "ms": round((time.monotonic() - started) * 1000),
            },
        )
        return response

    return app


def get_app() -> FastAPI:
    """Entry point for uvicorn: `uvicorn app.main:get_app --factory`."""
    return create_app()
