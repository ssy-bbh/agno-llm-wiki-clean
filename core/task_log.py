"""
core/task_log.py — Per-workspace task progress log (ingest/lint/autofill)
Captures print output from background flows into an in-memory ring buffer,
keyed by (user_id, workspace).
"""
import io
import sys
import time
import threading
from collections import deque, defaultdict
from datetime import datetime


class TaskLogManager:
    """Global singleton: stores per-(user, workspace) task logs."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._logs = defaultdict(lambda: deque(maxlen=2000))
                    cls._instance._meta = {}
                    cls._instance._log_lock = threading.Lock()
        return cls._instance

    def append(self, user_id: str, workspace: str, message: str, level: str = "info"):
        key = f"{user_id}:{workspace}"
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "timestamp": time.time(),
            "message": message,
            "level": level,
        }
        with self._log_lock:
            self._logs[key].append(entry)
            self._meta[key] = {
                "user_id": user_id,
                "workspace": workspace,
                "last_active": time.time(),
                "total_lines": len(self._logs[key]),
            }

    def get_logs(self, user_id: str = "", workspace: str = "", limit: int = 500, since: float = 0):
        with self._log_lock:
            if user_id and workspace:
                key = f"{user_id}:{workspace}"
                logs = list(self._logs.get(key, []))
            elif user_id:
                logs = []
                for k, v in self._logs.items():
                    if k.startswith(f"{user_id}:"):
                        logs.extend(list(v))
                logs.sort(key=lambda x: x.get("timestamp", 0))
            else:
                logs = []
                for v in self._logs.values():
                    logs.extend(list(v))
                logs.sort(key=lambda x: x.get("timestamp", 0))

        if since > 0:
            logs = [l for l in logs if l.get("timestamp", 0) > since]
        return logs[-limit:]

    def list_keys(self):
        """List all (user, workspace) pairs with metadata."""
        with self._log_lock:
            return [
                {**meta, "key": key}
                for key, meta in self._meta.items()
            ]

    def clear(self, user_id: str = "", workspace: str = ""):
        with self._log_lock:
            if user_id and workspace:
                key = f"{user_id}:{workspace}"
                self._logs.pop(key, None)
                self._meta.pop(key, None)
            elif user_id:
                to_remove = [k for k in self._logs if k.startswith(f"{user_id}:")]
                for k in to_remove:
                    self._logs.pop(k, None)
                    self._meta.pop(k, None)
            else:
                self._logs.clear()
                self._meta.clear()


# Singleton accessor
task_log = TaskLogManager()


class TaskOutputCapture:
    """
    Context manager that redirects stdout into the task log.
    Thread-safe: replaces sys.stdout only in the current thread.
    Also passes through to original stdout so journalctl still captures it.
    """

    def __init__(self, user_id: str, workspace: str):
        self.user_id = user_id
        self.workspace = workspace
        self._original_stdout = None

    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = _TeeWriter(self._original_stdout, task_log, self.user_id, self.workspace)
        return self

    def __exit__(self, *args):
        sys.stdout = self._original_stdout


class _TeeWriter(io.TextIOBase):
    """Writes to both original stdout and task log manager."""

    def __init__(self, original, log_mgr, user_id, workspace):
        self._original = original
        self._log = log_mgr
        self._uid = user_id
        self._ws = workspace
        self._buffer = ""

    def write(self, text):
        # Pass through to real stdout (so journalctl still works)
        try:
            self._original.write(text)
            self._original.flush()
        except Exception:
            pass

        # Buffer and split into lines for the task log
        if text:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                line = line.strip()
                if line:
                    level = "info"
                    if "❌" in line or "ERROR" in line or "失败" in line:
                        level = "error"
                    elif "⚠️" in line or "WARNING" in line:
                        level = "warning"
                    elif "✅" in line or "成功" in line or "完毕" in line:
                        level = "success"
                    self._log.append(self._uid, self._ws, line, level)
        return len(text) if text else 0

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass

    def fileno(self):
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, "encoding", "utf-8")

    def isatty(self):
        return False
