import asyncio
import base64

import docker
import requests

client = docker.from_env()


def _run_container_sync(
    language: str,
    code: str,
    stdin_data: str,
    timeout_sec: float,
    mem_limit_bytes: int,
    cpu_cores: float = 0.5,
) -> dict:
    if language != "python":
        return {
            "status": "error",
            "output": None,
            "error": f"Language {language} is not supported",
        }

    image = "python:3.11-alpine"

    encoded_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
    encoded_stdin = base64.b64encode(stdin_data.encode("utf-8")).decode("utf-8")

    command = (
        f"sh -c \"echo '{encoded_stdin}' | base64 -d | "
        f"python -c \\\"import base64; exec(base64.b64decode('{encoded_code}').decode('utf-8'))\\\"\""
    )

    container = None
    try:
        container = client.containers.run(
            image,
            command=command,
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
            return {"status": "error", "output": logs, "error": "Runtime Error"}

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
    task_time_limit: dict,
    task_memory_limit_bytes: int,
    stdin_data: str = "",
    cpu_cores: float = 0.5,  # hard-coded, because in tasks this parameter is not defined
) -> dict:
    seconds = task_time_limit.get("seconds", 0)
    nanos = task_time_limit.get("nanos", 0)
    timeout_sec = float(seconds + (nanos / 1_000_000_000.0))

    return await asyncio.to_thread(
        _run_container_sync,
        language,
        code,
        stdin_data,
        timeout_sec,
        task_memory_limit_bytes,
        cpu_cores,
    )
