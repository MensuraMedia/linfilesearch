"""
Search Manager
Streaming non-indexed search engine: one worker thread per root mountpoint,
cancellable/pausable, results and counters published through queues.
"""

import os
import re
import fnmatch
import threading
import queue
import time

from config.config_search import (
    MODE_SUBSTRING, MODE_WILDCARD, MODE_REGEX, SKIP_DIR_NAMES,
)


def make_matcher(query, mode, case_sensitive=False):
    """Build a name-matching predicate. Pure function (unit-tested)."""
    if not query:
        return None
    if mode == MODE_REGEX:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error:
            return lambda name: False

        def match(name):
            return pattern.search(name) is not None
        return match

    q = query if case_sensitive else query.lower()

    if mode == MODE_WILDCARD:
        def match(name):
            n = name if case_sensitive else name.lower()
            return fnmatch.fnmatchcase(n, q)
        return match

    def match(name):
        n = name if case_sensitive else name.lower()
        return q in n
    return match


class SearchStats:
    """Mutable counters shared between engine and UI."""

    def __init__(self):
        self.dirs_visited = 0
        self.matched = 0
        self.skipped = 0
        self.errors = 0
        self.started_at = None
        self.finished_at = False

    def snapshot(self):
        return {
            'dirs_visited': self.dirs_visited,
            'matched': self.matched,
            'skipped': self.skipped,
            'errors': self.errors,
            'elapsed': (time.monotonic() - self.started_at)
            if self.started_at and not self.finished_at
            else (self.elapsed_final or 0.0),
        }


class SearchEngine:
    """Run a search across one or more roots in background threads."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()          # set == running, clear == paused
        self.results = queue.Queue(maxsize=4096)
        self.stats = SearchStats()
        self.stats.elapsed_final = None
        self._workers = []
        self._lock = threading.Lock()

    # -- control ---------------------------------------------------------

    def start(self, roots, matcher, include_hidden=False, follow_symlinks=False):
        """Spawn one worker per root. Roots: list of absolute paths."""
        self.stop_event.clear()
        self.pause_event.set()
        self.stats = SearchStats()
        self.stats.elapsed_final = None
        self.stats.started_at = time.monotonic()
        self._workers = []
        for root in roots:
            t = threading.Thread(
                target=self._scan_root,
                args=(root, matcher, include_hidden, follow_symlinks),
                daemon=True, name=f'scan-{root}')
            t.start()
            self._workers.append(t)

    def pause(self):
        self.pause_event.clear()

    def resume(self):
        self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        self.pause_event.set()          # release paused workers so they exit
        self.stats.finished_at = True
        self.stats.elapsed_final = time.monotonic() - (self.stats.started_at or time.monotonic())

    @property
    def running(self):
        return any(t.is_alive() for t in self._workers)

    # -- scanning --------------------------------------------------------

    def _wait_if_paused(self):
        # block while paused, wake immediately on stop
        while not self.pause_event.wait(timeout=0.2):
            if self.stop_event.is_set():
                return

    def _scan_root(self, root, matcher, include_hidden, follow_symlinks):
        try:
            root_dev = os.stat(root).st_dev
        except OSError:
            with self._lock:
                self.stats.errors += 1
            self._finish_worker()
            return

        stack = [root]
        while stack:
            if self.stop_event.is_set():
                break
            self._wait_if_paused()
            if self.stop_event.is_set():
                break
            path = stack.pop()
            try:
                with os.scandir(path) as it:
                    entries = list(it)
            except (OSError, PermissionError):
                with self._lock:
                    self.stats.skipped += 1
                continue
            with self._lock:
                self.stats.dirs_visited += 1

            for entry in entries:
                if self.stop_event.is_set():
                    break
                name = entry.name
                try:
                    is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
                except OSError:
                    is_dir = False

                if not include_hidden and name.startswith('.'):
                    continue
                if is_dir:
                    if name in SKIP_DIR_NAMES:
                        continue
                    try:
                        if not follow_symlinks and entry.is_symlink():
                            continue
                        if os.stat(entry.path).st_dev != root_dev:
                            continue      # crossing into another filesystem
                    except OSError:
                        continue
                    stack.append(entry.path)
                    if matcher and matcher(name):
                        self._publish(entry.path, name, True, path)
                else:
                    if matcher and matcher(name):
                        try:
                            st = entry.stat(follow_symlinks=False)
                        except OSError:
                            st = None
                        self._publish(entry.path, name, False, path, st)
        self._finish_worker()

    def _publish(self, path, name, is_dir, parent, st=None):
        with self._lock:
            self.stats.matched += 1
        record = {
            'path': path, 'name': name, 'is_dir': is_dir,
            'size': (st.st_size if st else None),
            'mtime': (st.st_mtime if st else None),
        }
        while True:
            try:
                self.results.put(record, timeout=0.1)
                return
            except queue.Full:
                if self.stop_event.is_set():
                    return

    def _finish_worker(self):
        with self._lock:
            if not any(t.is_alive() for t in self._workers if t is not threading.current_thread()):
                self.stats.finished_at = True
                if self.stats.started_at and self.stats.elapsed_final is None:
                    self.stats.elapsed_final = time.monotonic() - self.stats.started_at
