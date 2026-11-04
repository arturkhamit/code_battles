# Sandbox runner

Runs user code for Code Battles. FastAPI sends `POST /run`; the runner compiles (C++) and judges the
code in locked-down containers and returns a verdict. FastAPI has no Docker socket and no `docker` package.

```
FastAPI --HTTP, Bearer RUNNER_TOKEN--> runner --tcp--> docker-socket-proxy --> /var/run/docker.sock
                                          |
                                          +-- starts: cb-sb-* sandbox containers (network none, ro rootfs, uid 10001, ...)
```

- The proxy filters endpoints, not bodies. So the runner builds every container spec itself
  (`app/spec.py`); a request carries only `language`, `code`, `tests`, and limits that are clamped.
- Code and tests travel on the container's stdin (a tar stream); the verdict comes back on stdout.
  `put_archive` is not used: Docker refuses it for a read-only container and cannot see a tmpfs.
- The judge (`sandbox/judge/judge.py`, stdlib only, inside each sandbox image) keeps the tests in its
  own memory, runs every test as a separate process with its own deadline, and is non-dumpable.
- Verdicts: OK, WA, TLE, RE, MLE, CE. Public tests first, then hidden (private + generated) to the first
  failure. Comparison is line by line, trailing whitespace and trailing empty lines ignored.
  A failed hidden test is only a number and a verdict.

## API

| | |
|---|---|
| `POST /run` | `{language: python\|cpp, code, tests: {public: [{input, output}], hidden: [...]}, time_limit_ms?, memory_limit_mb?}`. Bearer `RUNNER_TOKEN`. |
| `GET /health` | 200 while the process is alive. |
| `GET /ready` | 200 if Docker answers and both images exist, else 503 with the failed checks. |

Answer: `verdict`, `passed`, `total`, `failed_test` (`{number, hidden}` or null), `time_ms`, `memory_mb`
(null when the program is lighter than the judge itself), `detail` (public test only: input, expected,
actual, stderr, reason; each cut to 1 KiB), `compile_log` (CE, 2 KiB). 503 `busy` after
`RUNNER_QUEUE_TIMEOUT_SECONDS` without a free slot; 503 `sandbox_unavailable` when Docker or the judge fails.

Limits: time per test = task limit (default 2 s, max 10 s), whole run 60 s; memory = task limit within
[64, 512] MiB (256 when none), no swap; compile 512 MiB, 15 s, `-O2 -std=gnu++17 -pipe`, outside the task limit.
Container: `network none`, read-only rootfs, tmpfs `/tmp` (noexec, 16m) and `/work` (exec, 64m), `cap_drop ALL`,
`no-new-privileges`, pids 64, nofile 64, fsize 16 MiB, core 0, log driver `none`, label `cb.sandbox=1`.
A reaper removes `cb.sandbox=1` containers older than 2 minutes, at start and every minute.

## Configuration

`runner/.env.example` lists every variable. Required: `RUNNER_TOKEN` (32+ characters). Docker is
`SANDBOX_DOCKER_URL` (`tcp://docker-proxy:2375`, or `unix:///var/run/docker.sock` on a laptop without the proxy).

## Build the sandbox images

```
docker build -f runner/sandbox/python/Dockerfile -t code-battles-sandbox-python:1 runner/sandbox
docker build -f runner/sandbox/cpp/Dockerfile    -t code-battles-sandbox-cpp:1    runner/sandbox
```

Both bases are pinned by digest. Change the judge or a base: bump the tag (`:2`) and `SANDBOX_*_IMAGE`.
On a server, build the images before the first start (the runner never pulls) and check `/ready`.

## Run locally

```
RUNNER_TOKEN=$(openssl rand -hex 32) docker compose -f runner/docker-compose.dev.yml up -d --build
curl http://127.0.0.1:8002/ready
```

Then in `fastapi_app/.env`: `RUNNER_URL=http://localhost:8002` and the same `RUNNER_TOKEN`.

## Tests

```
cd runner && uv sync --frozen && .venv/bin/python -m pytest      # judge, spec, verdicts, HTTP layer; no Docker
```

Sandbox attack scenarios against a running stack: `qa/stage2/qa_scripts/s03b_sandbox_attacks.py`.
