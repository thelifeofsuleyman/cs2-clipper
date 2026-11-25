"""Read-only free-space checks for clips and the temporary replay buffer."""
import shutil
import threading
import time
from pathlib import Path

from . import paths


LOW_SPACE_BYTES = 2 * 1024**3


class StorageStatus:
    def __init__(self):
        self._root = paths.data_root()
        self.buffer = self._root / "buffer"
        self._lock = threading.Lock()
        self._check = None
        self._folder = None
        self._checked_at = 0.0
        self._status = {}

    def status(self, folder: str, buffer: Path) -> dict:
        selection = folder, buffer
        with self._lock:
            if self._check is None and (selection != self._folder or time.monotonic() - self._checked_at >= 15):
                self._check = threading.Thread(target=self._refresh, args=selection, daemon=True)
                self._check.start()
            return self._status.copy() if selection == self._folder else {}

    def _refresh(self, folder: str, buffer: Path) -> None:
        status = {}
        try:
            locations = {"clips": Path(folder) if folder else self._root, "buffer": buffer}
            for key, path in locations.items():
                try:
                    # Report a disconnected custom drive rather than a different drive's free space.
                    if not path.is_dir():
                        status[key] = {"available": False}
                        continue
                    free = shutil.disk_usage(path).free
                    status[key] = {"available": True, "free_bytes": free, "low": free < LOW_SPACE_BYTES}
                except (OSError, ValueError):
                    status[key] = {"available": False}
        finally:
            with self._lock:
                self._status = status
                self._folder = folder, buffer
                self._checked_at = time.monotonic()
                self._check = None
