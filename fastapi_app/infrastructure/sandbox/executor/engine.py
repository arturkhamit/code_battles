import asyncio

import docker
import requests

from .registry import LanguageRegistry

client = docker.from_env()


def _run_container_sync(
    language: str,
    code: str,
    stdin_data: list[str],
    single_test_timeout: float,
    mem_limit_bytes: int,
    cpu_cores: float = 0.5,
) -> dict:
    strategy = LanguageRegistry.get_strategy(language)

    if not strategy:
        return {
            "status": "error",
            "outputs": [],
            "error": f"Language {language} is not supported",
        }

    container = None
    total_timeout = (single_test_timeout * len(stdin_data)) + strategy.time_buffer

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

        result = container.wait(timeout=total_timeout)
        logs = container.logs().decode("utf-8").strip()

        if result["StatusCode"] == 0:
            outputs = logs.split("|||SPLIT|||")[:-1]
            outputs = [out.strip() for out in outputs]
            return {"status": "success", "outputs": outputs, "error": None}
        else:
            return {
                "status": "error",
                "outputs": [],
                "error": f"Runtime / Compilation Error:\n{logs}",
            }

    except requests.exceptions.ReadTimeout:
        if container:
            container.kill()
        return {
            "status": "error",
            "outputs": [],
            "error": f"Time Limit Exceeded (Batch timeout: {total_timeout}s)",
        }
    except Exception as e:
        return {"status": "error", "outputs": [], "error": f"Engine Error: {str(e)}"}
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
    stdin_data: list[str] = [""],
    cpu_cores: float = 0.5,
) -> dict:
    if task_time_limit:
        seconds = task_time_limit.get("seconds", 0)
        nanos = task_time_limit.get("nanos", 0)
        single_test_timeout = float(seconds + (nanos / 1_000_000_000.0))
    else:
        single_test_timeout = 1.0

    mem_limit = (
        task_memory_limit_bytes if task_memory_limit_bytes else 128 * 1024 * 1024
    )

    return await asyncio.to_thread(
        _run_container_sync,
        language,
        code,
        stdin_data,
        single_test_timeout,
        mem_limit,
        cpu_cores,
    )
