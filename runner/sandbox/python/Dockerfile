# Sandbox image for Python solutions. Build context: runner/sandbox (see runner/README.md):
#   docker build -f runner/sandbox/python/Dockerfile -t code-battles-sandbox-python:1 runner/sandbox
#
# Base: python:3.12-slim (Debian 13 trixie), pinned by digest. Bump on purpose, then the tag :1 -> :2
# (the runner takes the tag from SANDBOX_PYTHON_IMAGE):
#   docker buildx imagetools inspect python:3.12-slim
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

RUN groupadd --gid 10001 sandbox \
 && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin sandbox

# root-owned and read-only for the user: the program under test must not be able to change the judge
# (--chmod also applies to the directory the COPY creates: it needs the x bit)
COPY --chmod=0555 judge/judge.py /opt/judge/judge.py

# JUDGE_KILL_ALL: the judge kills every process of its uid after each test (sandbox only, see judge.py)
ENV JUDGE_KILL_ALL=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# /work is a tmpfs at run time (the runner mounts it); the directory only has to exist
WORKDIR /work
USER 10001:10001

ENTRYPOINT ["python", "-I", "-B", "/opt/judge/judge.py"]
CMD ["run"]
