# Sandbox image for C++ solutions: g++ on Debian slim, plus the same Python judge as the Python image.
# Build context: runner/sandbox (see runner/README.md):
#   docker build -f runner/sandbox/cpp/Dockerfile -t code-battles-sandbox-cpp:1 runner/sandbox
#
# Base: python:3.12-slim (Debian 13 trixie slim), pinned by digest. The same digest as the Python
# image, so both share their layers on disk. Bump on purpose, then the tag :1 -> :2.
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

# The apt versions float inside Debian 13: the repeatable part is the base digest above. A rebuild
# picks up security updates of g++; what matters for reproducibility is the image tag.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends g++ libc6-dev \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 sandbox \
 && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin sandbox

COPY --chmod=0555 judge/judge.py /opt/judge/judge.py

ENV JUDGE_KILL_ALL=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /work
USER 10001:10001

# "compile" builds /work/main from main.cpp and streams the binary out; "run" judges it.
ENTRYPOINT ["python", "-I", "-B", "/opt/judge/judge.py"]
CMD ["run"]
