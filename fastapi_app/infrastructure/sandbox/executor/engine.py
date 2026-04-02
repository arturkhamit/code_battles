import asyncio

import docker
import requests

from .registry import LanguageRegistry

client = docker.from_env()


def _run_container_sync(
    language: str,
    code: str,
    stdin_data: str,
    timeout_sec: float,
    mem_limit_bytes: int,
    cpu_cores: float = 0.5,
) -> dict:
    strategy = LanguageRegistry.get_strategy(language)

    if not strategy:
        return {
            "status": "error",
            "output": None,
            "error": f"Language {language} is not supported",
        }

    container = None
    try:
        container = client.containers.run(
            strategy.image,
            command=strategy.build_command(code, stdin_data),
            mem_limit=mem_limit_bytes,
            nano_cpus=int(cpu_cores * 1e9),
            network_disabled=True,
            detach=True,
            environment={"PYTHONUNBUFFERED": "1"},
        )

        result = container.wait(timeout=timeout_sec)
        logs = container.logs().decode("utf-8").strip()

        if result["StatusCode"] == 0:
            return {"status": "success", "output": logs, "error": None}
        else:
            return {
                "status": "error",
                "output": logs,
                "error": "Runtime Error / Compilation Error",
            }

    except requests.exceptions.ReadTimeout:
        if container:
            container.kill()
        return {
            "status": "error",
            "output": None,
            "error": f"Time Limit Exceeded ({timeout_sec}s)",
        }
    except Exception as e:
        return {"status": "error", "output": None, "error": f"Engine Error: {str(e)}"}
    finally:
        if container:
            try:
                container.remove(force=True)
            except docker.errors.APIError:
                pass


async def run_in_docker(
    language: str,
    code: str,
    task_time_limit: dict | None = None,
    task_memory_limit_bytes: int | None = None,
    stdin_data: str = "",
    cpu_cores: float = 0.5,
) -> dict:
    if task_time_limit:
        seconds = task_time_limit.get("seconds", 0)
        nanos = task_time_limit.get("nanos", 0)
        timeout_sec = float(seconds + (nanos / 1_000_000_000.0))
    else:
        timeout_sec = 5.0

    mem_limit = (
        task_memory_limit_bytes if task_memory_limit_bytes else 128 * 1024 * 1024
    )

    return await asyncio.to_thread(
        _run_container_sync,
        language,
        code,
        stdin_data,
        timeout_sec,
        mem_limit,
        cpu_cores,
    )
