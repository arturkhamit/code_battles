import json
from pathlib import Path


def get_json_tasks():
    current_dir = Path(__file__).resolve().parent

    file_path = current_dir / "tests.json"

    tasks = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                task = json.loads(line)
                tasks.append(task)

    return tasks
