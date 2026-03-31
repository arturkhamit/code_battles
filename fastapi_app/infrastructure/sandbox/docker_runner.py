import asyncio
import base64

import docker
import requests

from .limits import MAX_CPU_CORES, MAX_RAM_MB, TIMEOUT_SECONDS

client = docker.from_env()


def _run_container_sync(language: str, code: str, stdin_data: str = "") -> dict:
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
            mem_limit=f"{MAX_RAM_MB}m",
            nano_cpus=int(MAX_CPU_CORES * 1e9),
            network_disabled=True,
            detach=True,
            environment={"PYTHONUNBUFFERED": "1"},
        )

        result = container.wait(timeout=TIMEOUT_SECONDS)
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
            "error": f"Time Limit Exceeded ({TIMEOUT_SECONDS}s)",
        }
    except Exception as e:
        return {"status": "error", "output": None, "error": f"Engine Error: {str(e)}"}
    finally:
        if container:
            try:
                container.remove(force=True)
            except docker.errors.APIError:
                pass


async def run_in_docker(language: str, code: str, stdin_data: str = "") -> dict:
    return await asyncio.to_thread(_run_container_sync, language, code, stdin_data)
