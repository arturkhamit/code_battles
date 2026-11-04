"""Runner pieces that need no Docker: the container spec, the response builder, the wire format,
the reaper."""

import io
import json
import tarfile
import time

import pytest

from app import protocol, reaper, spec
from app.schemas import RunRequest
from app.verdict import KEEP, build_response


def request(public=1, hidden=2, language="python"):
    mk = lambda tag, n: [{"input": f"{tag}-in-{i}", "output": f"{tag}-out-{i}"} for i in range(n)]  # noqa: E731
    return RunRequest.model_validate(
        {"language": language, "code": "x", "tests": {"public": mk("pub", public), "hidden": mk("hid", hidden)}}
    )


# --- the container spec --------------------------------------------------------------------------


def test_the_spec_has_every_hardening_option():
    options = spec.container_options(
        image="img:1", command=["run"], name="cb-sb-x", mem_bytes=100 * spec.MIB, cpus=1.0
    )
    host, create = options.host, options.create
    assert host["network_mode"] == "none"
    assert host["read_only"] is True and host["init"] is True
    assert host["cap_drop"] == ["ALL"] and host["security_opt"] == ["no-new-privileges:true"]
    assert host["pids_limit"] == 64
    assert host["mem_limit"] == host["memswap_limit"] == 100 * spec.MIB  # no swap
    assert host["nano_cpus"] == 1_000_000_000
    assert host["tmpfs"]["/tmp"].startswith("rw,noexec,nosuid") and "size=16m" in host["tmpfs"]["/tmp"]
    assert "exec" in host["tmpfs"]["/work"].split(",") and "noexec" not in host["tmpfs"]["/work"]
    assert "nosuid" in host["tmpfs"]["/work"] and "size=64m" in host["tmpfs"]["/work"]
    ulimits = {u["Name"]: (u["Soft"], u["Hard"]) for u in host["ulimits"]}
    assert ulimits == {"nofile": (64, 64), "fsize": (16 * spec.MIB, 16 * spec.MIB), "core": (0, 0)}
    assert host["log_config"]["Type"] == "none"
    assert create["user"] == "10001:10001" and create["labels"] == {"cb.sandbox": "1"}
    assert create["stdin_open"] is True and create["detach"] is False


def test_the_spec_has_no_way_for_a_request_to_loosen_it():
    # nothing in the container options is built from user input except the limits, which are clamped
    keys = set(spec.container_options(image="i", command=["run"], name="n", mem_bytes=1, cpus=1).host)
    assert not keys & {"privileged", "binds", "volumes", "devices", "cap_add", "pid_mode", "userns_mode", "ipc_mode"}


@pytest.mark.parametrize(
    ("asked", "got"),
    [(None, 2000), (0, 2000), (1, 100), (500, 500), (2000, 2000), (10_000, 10_000), (60_000, 10_000)],
)
def test_time_limit_defaults_to_2s_and_is_capped_at_10s(asked, got):
    assert spec.time_limit_ms(asked) == got


@pytest.mark.parametrize(
    ("asked", "got"), [(None, 256), (0, 256), (32, 64), (61, 64), (64, 64), (200, 200), (512, 512), (1024, 512)]
)
def test_memory_is_the_tasks_within_64_and_512_mib(asked, got):
    assert spec.memory_limit_mb(asked) == got


def test_compile_has_more_memory_than_any_task_run():
    assert spec.COMPILE_MEMORY_MB >= spec.MAX_MEMORY_MB and spec.COMPILE_SECONDS == 15


# --- request validation --------------------------------------------------------------------------


def test_a_request_needs_tests_and_a_known_language():
    with pytest.raises(ValueError, match="no tests"):
        RunRequest.model_validate({"language": "python", "code": "x", "tests": {}})
    with pytest.raises(ValueError):
        RunRequest.model_validate({"language": "java", "code": "x", "tests": {"public": [{"input": "", "output": ""}]}})


# --- what may leave the runner -------------------------------------------------------------------


def judged(verdict, index, detail=None, **extra):
    return {"verdict": verdict, "passed": index, "failed_index": index, "time_ms": 30, "memory_kb": 20480,
            "detail": detail or {"actual": "ACTUAL", "stderr": "STDERR", "reason": "exit code 1"}, **extra}


def test_ok_reports_all_passed_and_the_numbers():
    out = build_response({"verdict": "OK", "passed": 3, "time_ms": 30, "memory_kb": 20480}, request())
    assert out == {"verdict": "OK", "passed": 3, "total": 3, "failed_test": None, "time_ms": 30, "memory_mb": 20.0}


def test_a_failed_public_test_shows_input_expected_actual_stderr():
    out = build_response(judged("RE", 0), request())
    assert out["failed_test"] == {"number": 1, "hidden": False}
    assert out["detail"] == {"input": "pub-in-0", "expected": "pub-out-0", "actual": "ACTUAL",
                             "stderr": "STDERR", "reason": "exit code 1"}


@pytest.mark.parametrize("verdict", ["WA", "TLE", "RE", "MLE"])
@pytest.mark.parametrize("index", [1, 2])
def test_a_failed_hidden_test_is_only_a_number_and_a_verdict(verdict, index):
    out = build_response(judged(verdict, index), request())
    assert out["failed_test"] == {"number": index + 1, "hidden": True}
    assert out["verdict"] == verdict and "detail" not in out
    blob = json.dumps(out)
    for leak in ("hid-in", "hid-out", "ACTUAL", "STDERR", "exit code"):
        assert leak not in blob


def test_public_details_are_cut_to_1_kib():
    big = "A" * 5000
    out = build_response(judged("WA", 0, {"actual": big, "stderr": big, "reason": None}), request())
    for field in ("actual", "stderr"):
        assert len(out["detail"][field]) < KEEP + 40 and out["detail"][field].endswith("(truncated)")


def test_compile_error_carries_the_log_cut_to_2_kib_and_no_failed_test():
    out = build_response({"verdict": "CE", "compile_log": "e" * 9000}, request())
    assert out["verdict"] == "CE" and out["failed_test"] is None and out["passed"] == 0
    assert 2048 < len(out["compile_log"]) < 2100


def test_a_verdict_the_runner_does_not_know_is_not_a_pass():
    assert build_response({"verdict": "PERFECT", "passed": 3}, request())["verdict"] == "RE"


def test_a_run_with_no_failed_index_has_no_failed_test():
    out = build_response({"verdict": "TLE", "passed": 0, "failed_index": None}, request())
    assert out["verdict"] == "TLE" and out["failed_test"] is None


# --- wire format ---------------------------------------------------------------------------------


def test_tar_roundtrip_and_record_padding():
    data = protocol.build_tar([("a.py", b"print(1)", 0o644), ("in/0", b"x" * 20_000, 0o644)])
    assert len(data) % 10240 == 0  # the judge's streaming reader reads whole records
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        assert {m.name: tar.extractfile(m).read() for m in tar} == {"a.py": b"print(1)", "in/0": b"x" * 20_000}


def frame(kind, payload):
    return bytes([kind, 0, 0, 0]) + len(payload).to_bytes(4, "big") + payload


def test_frames_split_stdout_and_stderr_even_when_cut_in_pieces():
    stream = frame(1, b"hello ") + frame(2, b"warn") + frame(1, b"world")
    frames = protocol.Frames(limit=1000)
    for i in range(0, len(stream), 5):  # arrives in 5-byte pieces
        frames.feed(stream[i : i + 5])
    assert bytes(frames.out) == b"hello world" and bytes(frames.err) == b"warn"


def test_frames_keep_at_most_the_limit():
    frames = protocol.Frames(limit=10)
    frames.feed(frame(1, b"x" * 100))
    assert len(frames.out) == 10 and frames.overflow


# --- reaper --------------------------------------------------------------------------------------


class FakeApi:
    def __init__(self, items):
        self.items, self.removed, self.filters = items, [], None

    def containers(self, all, filters):  # noqa: A002
        self.filters = filters
        return self.items

    def remove_container(self, container_id, force):
        assert force is True
        self.removed.append(container_id)


class FakeClient:
    def __init__(self, items):
        self.api = FakeApi(items)


def test_reaper_removes_only_old_labelled_containers():
    now = time.time()
    client = FakeClient([
        {"Id": "old" * 8, "Created": int(now - 300)},
        {"Id": "young" * 5, "Created": int(now - 30)},
        {"Id": "edge" * 6, "Created": int(now - reaper.MAX_AGE_SECONDS + 5)},
    ])
    assert reaper.reap(client, now=now) == 1
    assert client.api.removed == ["old" * 8]
    assert client.api.filters == {"label": ["cb.sandbox=1"]}
