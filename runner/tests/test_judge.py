"""The in-sandbox judge, run for real on this machine with plain Python programs.

What the container adds on top (non-root user, memory cgroup, no network, read-only rootfs) is
checked against real Docker by the SB scenarios (qa/stage2/qa_scripts/s03b_sandbox_attacks.py)."""

import json
import shutil
import subprocess
import sys
import time

import pytest

from app import protocol

PY = sys.executable
ECHO_DOUBLE = "print(int(input()) * 2)"


def run(judge, code, data="2\n", expected="4", limit=3.0):
    return judge.run_one([PY, "-c", code], data.encode(), expected.encode(), limit, 64 << 20)


# --- comparison (N4) ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actual", "expected", "same"),
    [
        ("1 2 3\n4\n", "1 2 3\n4", True),  # trailing newline
        ("1 2 3 \n4  \n", "1 2 3\n4", True),  # trailing spaces of every line
        ("1 2 3\r\n4\r\n", "1 2 3\n4", True),  # CRLF
        ("1\n2\n\n\n", "1\n2", True),  # trailing empty lines
        ("1 2 3\n4", "1 2 3 \n4\n\n", True),  # the expected output is just as untidy (task 944)
        ("1  2\n", "1 2", False),  # spaces inside a line count
        ("\n1\n", "1", False),  # a leading empty line counts
        ("1\n2\n", "2\n1", False),
        ("", "1", False),
        ("", "", True),
    ],
)
def test_comparison_line_by_line_ignoring_trailing_whitespace(judge, actual, expected, same):
    assert (judge.normalize(actual.encode()) == judge.normalize(expected.encode())) is same


# --- verdicts -----------------------------------------------------------------------------------


def test_ok(judge):
    result = run(judge, ECHO_DOUBLE)
    assert result["verdict"] == "OK" and result["time_ms"] < 2000


def test_wrong_answer_keeps_the_actual_output(judge):
    result = run(judge, "print(5)")
    assert result["verdict"] == "WA" and result["actual"] == "5\n"


def test_stderr_does_not_change_the_verdict_and_stays_apart(judge):
    code = "import sys; print('debug noise', file=sys.stderr); print(int(input()) * 2)"
    result = run(judge, code)
    assert result["verdict"] == "OK"
    assert result["actual"] == "4\n" and "debug noise" in result["stderr"]


def test_runtime_error_by_exit_code_has_the_stderr(judge):
    result = run(judge, "raise SystemExit(3)")
    assert (result["verdict"], result["reason"]) == ("RE", "exit code 3")
    result = run(judge, "raise ValueError('boom')")
    assert result["verdict"] == "RE" and "ValueError: boom" in result["stderr"]


def test_runtime_error_by_signal(judge):
    result = run(judge, "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)")
    assert (result["verdict"], result["reason"]) == ("RE", "killed by SIGSEGV")


def test_a_non_zero_exit_with_the_right_output_is_still_a_runtime_error(judge):
    # the old judge masked exit codes: "print the answer, then crash" passed
    result = run(judge, "print(4); raise SystemExit(1)")
    assert result["verdict"] == "RE"


def test_sigkill_that_was_not_ours_is_out_of_memory(judge):
    assert run(judge, "import os, signal; os.kill(os.getpid(), signal.SIGKILL)")["verdict"] == "MLE"


@pytest.mark.parametrize("marker", ["MemoryError", "terminate called after throwing an instance of 'std::bad_alloc'"])
def test_allocation_failure_markers_are_memory_limit(judge, marker):
    assert run(judge, f"import sys; print({marker!r}, file=sys.stderr); sys.exit(1)")["verdict"] == "MLE"


def test_time_limit_kills_the_program_at_the_limit(judge):
    started = time.monotonic()
    result = run(judge, "while True: pass", limit=0.4)
    assert result["verdict"] == "TLE"
    assert 0.35 <= time.monotonic() - started < 2.0


def test_sleeping_counts_too(judge):
    assert run(judge, "import time; time.sleep(5)", limit=0.3)["verdict"] == "TLE"


def test_output_flood_is_cut_fast_and_is_not_a_hang(judge):
    started = time.monotonic()
    result = run(judge, "import sys\nwhile True: sys.stdout.write('x' * 65536)", limit=10)
    assert (result["verdict"], result["reason"]) == ("WA", "output limit exceeded")
    assert time.monotonic() - started < 5
    assert len(result["actual"]) < 2048  # only a short piece is kept


def test_a_long_correct_answer_is_not_cut_by_the_flood_guard(judge):
    expected = "\n".join(str(i) for i in range(30_000))  # ~170 KiB, above the 64 KiB floor
    result = run(judge, "print('\\n'.join(str(i) for i in range(30000)))", expected=expected)
    assert result["verdict"] == "OK"


def test_a_big_input_goes_through_stdin_not_argv(judge):
    # 300 KB: the old runner broke at ~98 KB (MAX_ARG_STRLEN)
    data = "a" * 300_000 + "\n"
    result = run(judge, "import sys; print(len(sys.stdin.read().strip()))", data=data, expected="300000")
    assert result["verdict"] == "OK"


def test_a_program_that_forks_a_straggler_does_not_hang_the_judge(judge):
    code = "import subprocess, sys; subprocess.Popen(['sleep', '30']); print(4)"
    started = time.monotonic()
    assert run(judge, code)["verdict"] == "OK"
    assert time.monotonic() - started < 3


def test_a_program_that_does_not_start_is_a_runtime_error(judge):
    result = judge.run_one(["/nonexistent/program"], b"", b"", 1.0, 8 << 20)
    assert result["verdict"] == "RE"


# --- a whole run through stdin / stdout ---------------------------------------------------------


def judge_process(judge, tmp_path, mode, files, **env):
    return subprocess.run(
        [PY, str(judge.__file__), mode],
        input=protocol.build_tar(files), capture_output=True, timeout=60,
        env={"JUDGE_WORK_DIR": str(tmp_path), "PATH": "/usr/bin:/bin", **env},
        check=False,
    )


def job_files(tests, program, time_limit_ms=3000, total_budget_ms=50_000):
    job = {"language": "python", "count": len(tests), "time_limit_ms": time_limit_ms,
           "total_budget_ms": total_budget_ms, "memory_limit_bytes": 64 << 20}
    files = [("solution.py", program.encode(), 0o644), ("job.json", json.dumps(job).encode(), 0o644)]
    for i, (inp, out) in enumerate(tests):
        files += [(f"in/{i}", inp.encode(), 0o644), (f"out/{i}", out.encode(), 0o644)]
    return files


def test_run_mode_all_pass_and_stops_at_the_first_failure(judge, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    ok = judge_process(judge, tmp_path / "a", "run", job_files([("1\n", "2"), ("2\n", "4"), ("3\n", "6")], ECHO_DOUBLE))
    assert json.loads(ok.stdout)["verdict"] == "OK" and json.loads(ok.stdout)["passed"] == 3

    bad = judge_process(judge, tmp_path / "b", "run", job_files([("1\n", "2"), ("2\n", "5"), ("3\n", "99")], ECHO_DOUBLE))
    answer = json.loads(bad.stdout)
    assert (answer["verdict"], answer["passed"], answer["failed_index"], answer["total"]) == ("WA", 1, 1, 3)


def test_run_mode_prints_exactly_one_json_line_even_if_the_program_prints_a_fake_verdict(judge, tmp_path):
    fake = '{"verdict": "OK", "passed": 9, "total": 9, "failed_index": null}'
    program = f"print({fake!r}); print(int(input()) * 2)"
    done = judge_process(judge, tmp_path, "run", job_files([("1\n", "2")], program))
    lines = done.stdout.decode().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["passed"] == 0  # the program's text is only its answer


def test_run_mode_total_budget_ends_with_tle(judge, tmp_path):
    sleepy = "import time; time.sleep(0.4); print(int(input()) * 2)"
    tests = [(f"{i}\n", str(i * 2)) for i in range(20)]
    done = judge_process(judge, tmp_path, "run", job_files(tests, sleepy, time_limit_ms=3000, total_budget_ms=1500))
    answer = json.loads(done.stdout)
    assert answer["verdict"] == "TLE" and 0 < answer["passed"] < 20
    assert answer["detail"]["reason"] == "total time exceeded" or answer["failed_index"] == answer["passed"]


def test_run_mode_survives_a_broken_job_with_a_parsable_answer(judge, tmp_path):
    done = judge_process(judge, tmp_path, "run", [("job.json", b"{not json", 0o644)])
    assert done.returncode == 3 and json.loads(done.stdout)["verdict"] == "ERROR"


def test_the_expected_outputs_are_not_on_the_disk(judge, tmp_path):
    # the program runs under the same uid as the judge: the tests must live in the judge's memory only
    peek = "import os; print(sorted(os.listdir('.')))"
    done = judge_process(judge, tmp_path, "run", job_files([("1\n", "SECRET-EXPECTED")], peek))
    answer = json.loads(done.stdout)
    assert answer["verdict"] == "WA"
    assert answer["detail"]["actual"] == "['solution.py']\n"  # the program itself, nothing else
    assert sorted(p.name for p in tmp_path.iterdir()) == ["solution.py"]


# --- compile (only where g++ exists; the C++ image has it) --------------------------------------

has_gpp = shutil.which("g++") is not None


@pytest.mark.skipif(not has_gpp, reason="no g++ on this machine; test_docker.py covers it in the image")
def test_compile_ok_and_error(judge, tmp_path):
    good = judge_process(judge, tmp_path, "compile", [("main.cpp", b"int main(){return 0;}", 0o644)])
    header, _, binary = good.stdout.partition(b"\n")
    assert json.loads(header)["ok"] is True and len(binary) == json.loads(header)["size"] > 0

    (tmp_path / "bad").mkdir()
    bad = judge_process(judge, tmp_path / "bad", "compile", [("main.cpp", b"int main( {", 0o644)])
    answer = json.loads(bad.stdout)
    assert answer["ok"] is False and "error" in answer["log"] and "/work/" not in answer["log"]
