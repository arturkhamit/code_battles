import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JUDGE_PATH = ROOT / "sandbox" / "judge" / "judge.py"

# Settings are read when the app is created; a developer's runner/.env must not leak into tests.
os.environ.setdefault("RUNNER_TOKEN", "test-runner-token-0123456789abcdef0123456")
os.environ["ENVIRONMENT"] = "production"


@pytest.fixture(scope="session")
def judge_module():
    """The judge, imported from its file (it is not a package: it ships inside the sandbox images)."""
    spec = importlib.util.spec_from_file_location("sandbox_judge", JUDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def judge(judge_module, tmp_path, monkeypatch):
    monkeypatch.setattr(judge_module, "WORK", str(tmp_path))
    return judge_module
