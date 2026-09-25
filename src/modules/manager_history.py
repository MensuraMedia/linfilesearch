"""
History Manager
Tracks former searches (history) and bookmarked searches (saved), persisted
as JSON under ~/.config/linfilesearch/.
"""

import json
import os
import time
import threading
import uuid

HISTORY_CAP = 100


def _default_dir():
    return os.path.join(os.path.expanduser('~'), '.config', 'linfilesearch')


class HistoryManager:
    """Stores history and saved searches; JSON persistence; change callbacks."""

    def __init__(self, config_dir=None):
        self.config_dir = config_dir or _default_dir()
        self.history_path = os.path.join(self.config_dir, 'history.json')
        self.saved_path = os.path.join(self.config_dir, 'saved-searches.json')
        self.records = []      # newest last
        self.saved = []        # newest last
        self._callbacks = []
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------ storage

    def _load(self):
        for path, attr in ((self.history_path, 'records'),
                           (self.saved_path, 'saved')):
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    setattr(self, attr, data)
            except (OSError, ValueError):
                pass

    def _persist(self):
        os.makedirs(self.config_dir, exist_ok=True)
        tmp = self.history_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(self.records, fh, indent=2)
        os.replace(tmp, self.history_path)
        tmp = self.saved_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(self.saved, fh, indent=2)
        os.replace(tmp, self.saved_path)

    def on_change(self, callback):
        self._callbacks.append(callback)

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    # ------------------------------------------------------------ history

    def add(self, query, mode, case_sensitive, scope_kind, scope_paths):
        """Record a started search; returns the record."""
        record = {
            'id': uuid.uuid4().hex[:12],
            'time': time.strftime('%Y-%m-%d %H:%M:%S'),
            'query': query,
            'mode': mode,
            'case': bool(case_sensitive),
            'scope_kind': scope_kind,             # 'all' | 'paths'
            'scope_paths': list(scope_paths or []),
            'matches': None,
            'elapsed': None,
        }
        with self._lock:
            self.records.append(record)
            while len(self.records) > HISTORY_CAP:
                self.records.pop(0)
            self._persist()
        self._notify()
        return record

    def finish(self, record_id, matches, elapsed):
        """Patch a record with final counts after the search ends."""
        with self._lock:
            for rec in self.records:
                if rec['id'] == record_id:
                    rec['matches'] = matches
                    rec['elapsed'] = round(elapsed, 1) if elapsed else None
                    break
            else:
                return
            self._persist()
        self._notify()

    def clear(self):
        with self._lock:
            self.records = []
            self._persist()
        self._notify()

    # -------------------------------------------------------------- saved

    @staticmethod
    def _signature(record):
        return (record.get('query'), record.get('mode'),
                bool(record.get('case')),
                tuple(record.get('scope_paths') or []),
                record.get('scope_kind'))

    def is_saved(self, record):
        sig = self._signature(record)
        return any(self._signature(s) == sig for s in self.saved)

    def bookmark(self, record):
        """Copy a history record into Saved (deduped)."""
        if self.is_saved(record):
            return False
        saved = dict(record)
        saved['saved_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with self._lock:
            self.saved.append(saved)
            self._persist()
        self._notify()
        return True

    def remove_saved(self, record_id):
        with self._lock:
            before = len(self.saved)
            self.saved = [s for s in self.saved if s.get('id') != record_id]
            if len(self.saved) == before:
                return False
            self._persist()
        self._notify()
        return True

    def scope_display(self, record):
        if record.get('scope_kind') == 'all':
            return 'All mountpoints'
        paths = record.get('scope_paths') or []
        return ', '.join(paths) if paths else 'All mountpoints'
