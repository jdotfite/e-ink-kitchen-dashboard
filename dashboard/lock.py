from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path


@contextmanager
def single_instance(lock_file: Path):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("w") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Another dashboard update is already running: {lock_file}") from exc
        yield
