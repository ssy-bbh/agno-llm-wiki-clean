"""
core/task_log.py — Per-workspace task progress log (ingest/lint/autofill)
Captures print output from background flows into an in-memory ring buffer,
keyed by (user_id, workspace).
Progress data is also written to shared files for multi-worker visibility.
"""
import io
import json
import re
import sys
import time
import threading
from collections import deque, defaultdict
from datetime import datetime
from pathlib import Path


class TaskLogManager:
    """Global singleton: stores per-(user, workspace) task logs + structured progress."""

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
                    cls._instance._progress = {}  # key -> structured progress
                    cls._instance._progress_lock = threading.Lock()
        return cls._instance

    # ── 结构化进度追踪 ──
    # ── 文件持久化路径（跨 worker 共享） ──
    _PROGRESS_DIR = Path(__file__).resolve().parent.parent / "data" / ".ingest_status"

    def _progress_file(self, user_id: str, workspace: str) -> Path:
        self._PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        return self._PROGRESS_DIR / f"{user_id}__{workspace}_progress.json"

    def set_progress(self, user_id: str, workspace: str, **kwargs):
        """Update structured progress for a (user, workspace) pair.
        Also writes to a shared file for multi-worker visibility."""
        key = f"{user_id}:{workspace}"
        with self._progress_lock:
            if key not in self._progress:
                self._progress[key] = {
                    "phase": "idle",
                    "current_file": 0,
                    "total_files": 0,
                    "current_file_name": "",
                    "total_chunks": 0,
                    "map_done": 0,
                    "total_concepts": 0,
                    "reduce_done": 0,
                    "started": 0,
                }
            self._progress[key].update(kwargs)
            self._progress[key]["updated"] = time.time()
            snapshot = dict(self._progress[key])
        # Write to shared file (non-blocking best-effort)
        try:
            self._progress_file(user_id, workspace).write_text(
                json.dumps(snapshot), encoding="utf-8"
            )
        except Exception:
            pass

    def get_progress(self, user_id: str, workspace: str) -> dict:
        """Read progress: prefer in-memory, fallback to shared file."""
        key = f"{user_id}:{workspace}"
        with self._progress_lock:
            mem = self._progress.get(key)
            if mem:
                return dict(mem)
        # Fallback: read from file (cross-worker)
        try:
            fpath = self._progress_file(user_id, workspace)
            if fpath.exists():
                data = json.loads(fpath.read_text(encoding="utf-8"))
                # Cache it in memory for fast subsequent reads
                with self._progress_lock:
                    self._progress[key] = data
                return data
        except Exception:
            pass
        return {"phase": "idle"}

    def clear_progress(self, user_id: str = "", workspace: str = ""):
        with self._progress_lock:
            if user_id and workspace:
                self._progress.pop(f"{user_id}:{workspace}", None)
            elif user_id:
                to_remove = [k for k in self._progress if k.startswith(f"{user_id}:")]
                for k in to_remove:
                    self._progress.pop(k, None)
            else:
                self._progress.clear()

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
    """Writes to both original stdout and task log manager.
    Also auto-parses progress patterns to update structured progress."""

    # Compiled regex patterns for progress extraction
    _RE_FILE_PROGRESS = re.compile(r'\[(\d+)/(\d+)\]\s*提取:\s*(.+)\s*->')
    _RE_CHUNKS = re.compile(r'✂️\s*物理切分为\s*(\d+)\s*个知识块')
    _RE_MAP_DONE = re.compile(r'✅\s*线程\s*\d+\s*提取完毕')
    _RE_SHUFFLE = re.compile(r'Phase 2:\s*SHUFFLE')
    _RE_REDUCE_TOTAL = re.compile(r'发现\s*(\d+)\s*个独立核心概念')
    _RE_REDUCE_PROGRESS = re.compile(r'\[融合\s*(\d+)/(\d+)\]')
    _RE_COMPLETE = re.compile(r'提炼完成|全部完成|摄入完毕')
    _RE_MAP_START = re.compile(r'Phase 1:\s*MAP')

    def __init__(self, original, log_mgr, user_id, workspace):
        self._original = original
        self._log = log_mgr
        self._uid = user_id
        self._ws = workspace
        self._buffer = ""

    def _update_progress(self, line: str):
        """Parse a stdout line and update structured progress if it matches a pattern."""
        # File-level progress: [1/3] 提取: xxx.pdf -> workspace
        m = self._RE_FILE_PROGRESS.search(line)
        if m:
            self._log.set_progress(
                self._uid, self._ws,
                phase="parsing",
                current_file=int(m.group(1)),
                total_files=int(m.group(2)),
                current_file_name=m.group(3).strip(),
                total_chunks=0, map_done=0, total_concepts=0, reduce_done=0,
            )
            return

        # Chunk count
        m = self._RE_CHUNKS.search(line)
        if m:
            self._log.set_progress(self._uid, self._ws, total_chunks=int(m.group(1)), phase="extracting")
            return

        # MAP start
        if self._RE_MAP_START.search(line):
            self._log.set_progress(self._uid, self._ws, phase="extracting", map_done=0)
            return

        # MAP chunk done
        if self._RE_MAP_DONE.search(line):
            prog = self._log.get_progress(self._uid, self._ws)
            self._log.set_progress(self._uid, self._ws, map_done=prog.get("map_done", 0) + 1, phase="extracting")
            return

        # SHUFFLE phase
        if self._RE_SHUFFLE.search(line):
            self._log.set_progress(self._uid, self._ws, phase="clustering")
            return

        # REDUCE total concepts
        m = self._RE_REDUCE_TOTAL.search(line)
        if m:
            self._log.set_progress(self._uid, self._ws, total_concepts=int(m.group(1)), phase="merging", reduce_done=0)
            return

        # REDUCE per-concept progress
        m = self._RE_REDUCE_PROGRESS.search(line)
        if m:
            self._log.set_progress(self._uid, self._ws, reduce_done=int(m.group(1)), phase="merging")
            return

        # Complete
        if self._RE_COMPLETE.search(line):
            self._log.set_progress(self._uid, self._ws, phase="done")
            return

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
                    # Update structured progress
                    self._update_progress(line)

                    # Write to log ring buffer
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
