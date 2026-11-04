"""Talking to the judge: a tar stream in through the container's stdin, frames out through stdout.

Why not put_archive: Docker refuses to copy into a read-only container unless the target is a
volume, and a tmpfs (what /work has to be) is invisible to it. So the files travel on stdin and
the judge puts them where they belong.
"""

import io
import socket
import tarfile
import time

STDOUT, STDERR = 1, 2
FRAME_HEADER = 8


def build_tar(files: list[tuple[str, bytes, int]]) -> bytes:
    """(name, data, mode) -> tar bytes, padded to the 10240-byte record so that the judge's
    streaming reader never waits for bytes that are not coming."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data, mode in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Frames:
    """Splits Docker's multiplexed attach stream (8-byte header: stream, 3 zero bytes, size) into
    stdout and stderr. Keeps at most `limit` bytes of each and drops the rest."""

    def __init__(self, limit: int):
        self.limit = limit
        self.out = bytearray()
        self.err = bytearray()
        self._buf = bytearray()
        self.overflow = False

    def feed(self, chunk: bytes) -> None:
        self._buf += chunk
        while len(self._buf) >= FRAME_HEADER:
            size = int.from_bytes(self._buf[4:8], "big")
            if len(self._buf) < FRAME_HEADER + size:
                return
            kind = self._buf[0]
            payload = self._buf[FRAME_HEADER : FRAME_HEADER + size]
            del self._buf[: FRAME_HEADER + size]
            sink = self.out if kind == STDOUT else self.err if kind == STDERR else None
            if sink is None:
                continue
            room = self.limit - len(sink)
            sink += payload[:room]
            if len(payload) > room:
                self.overflow = True


def send_all(raw: socket.socket, data: bytes, deadline: float) -> bool:
    """Send the tar and half-close. False if the container is gone before it took everything."""
    try:
        raw.settimeout(max(0.1, deadline - time.monotonic()))
        raw.sendall(data)
        raw.shutdown(socket.SHUT_WR)
    except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
        return False
    return True


def read_until_closed(raw: socket.socket, frames: Frames, deadline: float) -> bool:
    """Read until the stream ends (the container exited). True = ended, False = out of time."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        raw.settimeout(remaining)
        try:
            chunk = raw.recv(65536)
        except (TimeoutError, socket.timeout):
            return False
        except (ConnectionResetError, OSError):
            return True
        if not chunk:
            return True
        frames.feed(chunk)
