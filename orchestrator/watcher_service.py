"""
Watched directory service.

Uses watchdog to monitor filesystem paths and trigger autonomous AI processing
when new files are detected. Each watched directory has its own console log
that streams to the frontend via SSE.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Optional, Callable, List, Set

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class _Handler(FileSystemEventHandler):
    """Bridges OS file events into the asyncio event queue."""

    def __init__(self, dir_id: str, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):
        super().__init__()
        self.dir_id = dir_id
        self.loop = loop
        self.queue = queue

    def on_created(self, event):
        if not event.is_directory:
            asyncio.run_coroutine_threadsafe(
                self.queue.put((self.dir_id, event.src_path)),
                self.loop
            )


class WatcherService:
    def __init__(self):
        self._observers: Dict[str, Observer] = {}
        self._debounce_tasks: Dict[str, asyncio.Task] = {}
        self._pending_files: Dict[str, Set[str]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None
        self._execute_callback: Optional[Callable] = None
        self._console_log: List[Dict] = []

    def set_execute_callback(self, callback: Callable):
        self._execute_callback = callback

    def push_console(self, dir_id: str, message: str):
        entry = {
            "dir_id": dir_id,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self._console_log.append(entry)
        if len(self._console_log) > 1000:
            self._console_log.pop(0)
        print(f"[watcher:{dir_id[:8]}] {message}")

    def get_console_log(self, dir_id: Optional[str] = None) -> List[Dict]:
        if dir_id:
            return [e for e in self._console_log if e["dir_id"] == dir_id]
        return list(self._console_log)

    def start_watching(self, dir_id: str, path: str, name: str) -> bool:
        if dir_id in self._observers:
            self.stop_watching(dir_id)

        if not os.path.isdir(path):
            self.push_console(dir_id, f"[ERROR] Path does not exist: {path}")
            return False

        try:
            loop = asyncio.get_event_loop()
            handler = _Handler(dir_id, loop, self._event_queue)
            observer = Observer()
            observer.schedule(handler, path, recursive=True)
            observer.start()
            self._observers[dir_id] = observer
            self._pending_files[dir_id] = set()
            self.push_console(dir_id, f"[INFO] Watching started: {path}")
            return True
        except Exception as e:
            self.push_console(dir_id, f"[ERROR] Failed to start watcher: {e}")
            return False

    def stop_watching(self, dir_id: str):
        if dir_id in self._observers:
            try:
                self._observers[dir_id].stop()
                self._observers[dir_id].join(timeout=2)
            except Exception:
                pass
            del self._observers[dir_id]
        if dir_id in self._debounce_tasks:
            self._debounce_tasks[dir_id].cancel()
            del self._debounce_tasks[dir_id]
        self._pending_files.pop(dir_id, None)
        self.push_console(dir_id, "[INFO] Watching stopped.")

    def is_watching(self, dir_id: str) -> bool:
        obs = self._observers.get(dir_id)
        return obs is not None and obs.is_alive()

    async def _process_events(self):
        """Consume file events from the queue and debounce per directory."""
        while True:
            try:
                dir_id, file_path = await asyncio.wait_for(self._event_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return

            if dir_id not in self._pending_files:
                self._pending_files[dir_id] = set()
            self._pending_files[dir_id].add(file_path)
            self.push_console(dir_id, f"[FILE] Detected: {os.path.basename(file_path)}")

            # Reset debounce: wait 3s after the last file lands before triggering
            if dir_id in self._debounce_tasks:
                self._debounce_tasks[dir_id].cancel()
            self._debounce_tasks[dir_id] = asyncio.create_task(
                self._debounce_trigger(dir_id)
            )

    async def _debounce_trigger(self, dir_id: str):
        await asyncio.sleep(3.0)
        files = sorted(self._pending_files.get(dir_id, set()))
        if dir_id in self._pending_files:
            self._pending_files[dir_id] = set()
        if not files or not self._execute_callback:
            return
        self.push_console(dir_id, f"[INFO] Triggering AI for {len(files)} file(s)...")
        try:
            await self._execute_callback(dir_id, files)
        except Exception as e:
            self.push_console(dir_id, f"[ERROR] AI execution failed: {e}")

    async def start(self):
        self._processor_task = asyncio.create_task(self._process_events())

    async def stop(self):
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        for dir_id in list(self._observers.keys()):
            self.stop_watching(dir_id)


# Global singleton
watcher_service = WatcherService()
