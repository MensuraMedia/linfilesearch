"""Unit tests for the history/saved store (pure logic, temp dirs)."""

import json
import os

import pytest

from modules.manager_history import HistoryManager


@pytest.fixture()
def store(tmp_path):
    return HistoryManager(config_dir=str(tmp_path / 'cfg'))


def _run(store, query='*report*.odt', mode='wildcard', case=False, kind='all'):
    return store.add(query=query, mode=mode, case_sensitive=case,
                     scope_kind=kind, scope_paths=[] if kind == 'all' else ['/home'])


def test_add_and_persist(store, tmp_path):
    rec = _run(store)
    assert store.records and store.records[0]['query'] == '*report*.odt'
    data = json.load(open(os.path.join(str(tmp_path / 'cfg'), 'history.json')))
    assert data[0]['id'] == rec['id']


def test_reload_from_disk(store, tmp_path):
    _run(store, query='budget')
    store2 = HistoryManager(config_dir=str(tmp_path / 'cfg'))
    assert [r['query'] for r in store2.records] == ['budget']


def test_finish_patches_record(store):
    rec = _run(store)
    store.finish(rec['id'], matches=42, elapsed=3.2)
    assert store.records[0]['matches'] == 42
    assert store.records[0]['elapsed'] == 3.2


def test_clear(store):
    _run(store)
    _run(store, query='other')
    store.clear()
    assert store.records == []
    assert not os.path.exists(store.history_path) or json.load(open(store.history_path)) == []


def test_history_cap(store):
    for i in range(120):
        _run(store, query=f'q{i}')
    assert len(store.records) == 100
    assert store.records[-1]['query'] == 'q119'


def test_bookmark_dedupe(store):
    rec = _run(store)
    assert store.bookmark(rec) is True
    assert store.bookmark(dict(rec)) is False      # same signature twice
    assert len(store.saved) == 1
    assert store.is_saved(rec)


def test_remove_saved(store):
    rec = _run(store)
    store.bookmark(rec)
    assert store.remove_saved(rec['id']) is True
    assert store.remove_saved(rec['id']) is False
    assert store.saved == []


def test_scope_display(store):
    rec = _run(store, kind='all')
    assert store.scope_display(rec) == 'All mountpoints'
    rec2 = store.add(query='x', mode='substring', case_sensitive=True,
                     scope_kind='paths', scope_paths=['/mnt/data'])
    assert store.scope_display(rec2) == '/mnt/data'
