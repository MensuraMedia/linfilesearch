"""
Search Manager
Streaming non-indexed search engine: one worker thread per root mountpoint,
cancellable/pausable, results and counters published through queues.

r025 hardening (adversarial review):
- completion decided by a pending-worker counter, not is_alive() probing
  (the old race could leave a finished search stuck "running")
- zero roots finish immediately instead of spinning forever
- roots are deduplicated and same-filesystem nested roots dropped
  (bind mounts used to publish every match twice)
- each record carries the root it was found under (true Mount column)
- matched is counted only after the record is actually queued
- paused time is excluded from elapsed
- directories publish their real mtime
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
    """Build a name-matching predicate. Pure function (unit-tested).

    Raises ValueError for an invalid regex so the caller can report it
    instead of silently scanning to "0 matches".
    """
    if not query:
        return None
    if mode == MODE_REGEX:
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            raise ValueError(f'Invalid regular expression: {e}') from e

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
        self.stopped = False
        self.paused_total = 0.0
        self.elapsed_final = None
        self.pause_started = None

    def snapshot(self):
        if self.started_at is None:
            elapsed = 0.0
        elif self.finished_at:
            elapsed = self.elapsed_final or 0.0
        else:
            live_pause = 0.0
            if self.pause_started is not None:
                live_pause = max(0.0, time.monotonic() - self.pause_started)
            elapsed = (time.monotonic() - self.started_at
                       - self.paused_total - live_pause)
        return {
            'dirs_visited': self.dirs_visited,
            'matched': self.matched,
            'skipped': self.skipped,
            'errors': self.errors,
            'stopped': self.stopped,
            'elapsed': max(0.0, elapsed),
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
        self.stats.pause_started = None
        self._workers = []
        self._pending_workers = 0
        self._lock = threading.Lock()

    # -- control ---------------------------------------------------------

    def start(self, roots, matcher, include_hidden=False, follow_symlinks=False):
        """Spawn one worker per root. Roots: list of absolute paths."""
        self.stop_event.clear()
        self.pause_event.set()
        self.stats = SearchStats()
        self.stats.elapsed_final = None
        self.stats.pause_started = None
        self.stats.started_at = time.monotonic()
        self._workers = []
        roots = self._normalize_roots(roots)
        self._pending_workers = len(roots)
        if not roots:
            # nothing to scan: finish immediately so the UI reaches Done
            self.stats.finished_at = True
            self.stats.elapsed_final = 0.0
            return
        for root in roots:
            t = threading.Thread(
                target=self._scan_root,
                args=(root, matcher, include_hidden, follow_symlinks),
                daemon=True, name=f'scan-{root}')
            t.start()
            self._workers.append(t)

    @staticmethod
    def _normalize_roots(roots):
        """Deduplicate roots; drop roots nested inside another root on the
        same filesystem (bind mounts / remounts), which would otherwise
        publish every shared match twice."""
        unique = list(dict.fromkeys(os.path.abspath(r) for r in roots))
        devs = {}
        for r in unique:
            try:
                devs[r] = os.stat(r).st_dev
            except OSError:
                pass
        kept = []
        for r in sorted(unique, key=len):
            nested = any(
                r != k and r.startswith(k.rstrip('/') + '/')
                and devs.get(r) == devs.get(k)
                for k in kept)
            if not nested:
                kept.append(r)
        return kept

    def pause(self):
        if self.stats.pause_started is None:
            self.stats.pause_started = time.monotonic()
        self.pause_event.clear()

    def resume(self):
        with self._lock:
            if self.stats.pause_started is not None:
                self.stats.paused_total += (
                    time.monotonic() - self.stats.pause_started)
                self.stats.pause_started = None
        self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        with self._lock:
            if self.stats.pause_started is not None:
                self.stats.paused_total += (
                    time.monotonic() - self.stats.pause_started)
                self.stats.pause_started = None
        self.pause_event.set()          # release paused workers so they exit
        self.stats.finished_at = True
        self.stats.stopped = True
        elapsed = time.monotonic() - (self.stats.started_at or time.monotonic())
        self.stats.elapsed_final = max(0.0, elapsed - self.stats.paused_total)

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
                        dst = os.stat(entry.path)
                        if dst.st_dev != root_dev:
                            continue      # crossing into another filesystem
                    except OSError:
                        continue
                    stack.append(entry.path)
                    if matcher and matcher(name):
                        self._publish(root, entry.path, name, True, path, dst)
                else:
                    if matcher and matcher(name):
                        try:
                            st = entry.stat(follow_symlinks=False)
                        except OSError:
                            st = None
                        self._publish(root, entry.path, name, False, path, st)
        self._finish_worker()

    def _publish(self, root, path, name, is_dir, parent, st=None):
        record = {
            'path': path, 'name': name, 'is_dir': is_dir, 'root': root,
            'size': (st.st_size if st else None),
            'mtime': (st.st_mtime if st else None),
        }
        while True:
            try:
                self.results.put(record, timeout=0.1)
                with self._lock:
                    self.stats.matched += 1
                return
            except queue.Full:
                if self.stop_event.is_set():
                    return

    def _finish_worker(self):
        with self._lock:
            self._pending_workers -= 1
            if self._pending_workers > 0:
                return
            self.stats.finished_at = True
            if self.stats.started_at is not None and self.stats.elapsed_final is None:
                elapsed = time.monotonic() - self.stats.started_at
                self.stats.elapsed_final = max(0.0, elapsed - self.stats.paused_total)
