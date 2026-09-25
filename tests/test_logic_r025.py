"""r025 fixes from the adversarial review.

Engine: completion decided by a worker counter (the old is_alive race could
leave a search stuck 'running'), zero-root searches finish, overlapping
same-fs roots no longer double-publish, records carry their root and
directories their mtime, matched only counts queued rows, paused time is
excluded from elapsed.

Page: wildcard metachars in substring mode auto-switch with a notice (the
'LinShot* found nothing' trap), invalid regexes surface instead of scanning
to a fake zero, scope chips survive a repopulate, Modified sorts on a hidden
epoch column, columns keep readable minimum widths, stopped searches say
Stopped and are flagged in history.
"""

import os
import time

import pytest

from modules.manager_search import SearchEngine, make_matcher
from config.config_search import (
    MODE_SUBSTRING, MODE_WILDCARD, MODE_REGEX)

# --------------------------------------------------------------- engine


def _wait_finished(engine, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if engine.stats.finished_at:
            return True
        time.sleep(0.005)
    return False


def _drain(engine):
    rows = []
    while True:
        try:
            rows.append(engine.results.get_nowait())
        except Exception:
            return rows


def test_two_fast_roots_always_finish(tmp_path):
    # regression for the is_alive finish race (31-89 hangs per 400 runs)
    match_all = make_matcher('*', MODE_WILDCARD)
    for _ in range(60):
        engine = SearchEngine()
        engine.start([str(tmp_path / 'a'), str(tmp_path / 'b')], match_all)
        assert _wait_finished(engine), 'search finished state never arrived'
        assert engine.stats.stopped is False


def test_zero_roots_finish_immediately():
    engine = SearchEngine()
    engine.start([], make_matcher('x', MODE_SUBSTRING))
    assert engine.stats.finished_at is True
    assert engine.stats.snapshot()['elapsed'] == 0.0


def test_overlapping_same_fs_roots_do_not_duplicate(tmp_path):
    root = tmp_path / 'root'
    (root / 'sub').mkdir(parents=True)
    for name in ('one.txt', 'two.txt'):
        (root / name).write_text('x')
    (root / 'sub' / 'three.txt').write_text('x')

    engine = SearchEngine()
    engine.start([str(root), str(root / 'sub')],
                 make_matcher('*', MODE_WILDCARD))
    assert _wait_finished(engine)
    rows = _drain(engine)
    paths = [r['path'] for r in rows]
    # 2 files + the sub dir itself + the file inside it; no duplicates
    assert len(paths) == len(set(paths)) == 4, \
        f'overlapping roots must not double-publish: {paths}'
    assert engine.stats.matched == 4


def test_duplicate_root_entries_are_deduped(tmp_path):
    d = tmp_path / 'd'
    d.mkdir()
    (d / 'f.txt').write_text('x')
    engine = SearchEngine()
    engine.start([str(d), str(d)], make_matcher('*', MODE_WILDCARD))
    assert _wait_finished(engine)
    assert len(_drain(engine)) == 1


def test_records_carry_root_and_directory_mtime(tmp_path):
    root = tmp_path / 'r'
    sub = root / 'alpha'
    sub.mkdir(parents=True)
    (sub / 'file.txt').write_text('x')
    engine = SearchEngine()
    engine.start([str(root)], make_matcher('*', MODE_WILDCARD))
    assert _wait_finished(engine)
    rows = _drain(engine)
    dirs = [r for r in rows if r['is_dir']]
    assert dirs and dirs[0]['root'] == str(root), \
        'records must carry the root they were found under'
    assert dirs[0]['mtime'] is not None, \
        'directory rows must publish their real mtime'


def test_matched_equals_queued_rows_after_stop(tmp_path):
    root = tmp_path / 'many'
    root.mkdir()
    for i in range(50):
        (root / f'f{i}.txt').write_text('x')
    engine = SearchEngine()
    engine.start([str(root)], make_matcher('*', MODE_WILDCARD))
    time.sleep(0.05)
    engine.stop()
    rows = _drain(engine)
    assert len(rows) == engine.stats.matched, \
        'matched must count only rows actually queued'
    assert engine.stats.stopped is True


def test_pause_time_excluded_from_elapsed():
    engine = SearchEngine()
    engine.start([], make_matcher('x', MODE_SUBSTRING))
    engine.pause()
    time.sleep(0.25)
    engine.resume()
    engine.stop()
    assert engine.stats.paused_total >= 0.2
    assert engine.stats.snapshot()['elapsed'] < 0.1


# ------------------------------------------------------- page-level (X)

display = pytest.mark.skipif(
    not os.environ.get('DISPLAY'), reason='needs an X display')


@display
def test_wildcard_metachars_auto_switch(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import ui.dashboard_window  # noqa: F401  (import order)
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    (tmp_path / 'LinShot_2026.png').write_bytes(b'\x89PNG')
    page.selected_roots = lambda: [str(tmp_path)]
    page.query_entry.set_text('LinShot*')     # substring mode default
    assert page.mode == MODE_SUBSTRING
    page.start_search()
    assert page.mode == MODE_WILDCARD, \
        'glob metachars in substring mode must switch to wildcard'
    assert 'wildcard' in page.status_scan.get_text().lower()
    end = time.monotonic() + 5.0
    while page.engine is not None and time.monotonic() < end:
        page._drain_results()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)
    assert page.engine is None
    assert len(page.store) == 1, 'LinShot* must find the file after switching'
    # Mount column shows the true root, not a startswith guess
    assert page.store[0][6] == str(tmp_path)


@display
def test_invalid_regex_surfaces_without_scanning(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    history = HistoryManager(config_dir=str(tmp_path / 'cfg'))
    page = SearchPage(MountManager(), history)
    page.selected_roots = lambda: [str(tmp_path)]
    page.mode = MODE_REGEX
    page.query_entry.set_text('([unclosed')
    page.start_search()
    assert page.engine is None, 'invalid regex must not start a scan'
    assert 'Invalid regular expression' in page.status_scan.get_text()
    assert len(history.records) == 0


@display
def test_no_searchable_roots_message(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    page.selected_roots = lambda: []
    page.query_entry.set_text('anything')
    page.start_search()
    assert page.engine is None
    assert page.status_scan.get_text() == 'No searchable mountpoints found.'


@display
def test_stopped_search_says_stopped_and_flags_history(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    history = HistoryManager(config_dir=str(tmp_path / 'cfg'))
    page = SearchPage(MountManager(), history)
    page.selected_roots = lambda: [str(tmp_path)]
    page.query_entry.set_text('*')
    page.start_search()
    assert page._search_state == 'running'
    page.stop_search()
    end = time.monotonic() + 5.0
    while page.engine is not None and time.monotonic() < end:
        page._drain_results()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)
    assert page.status_scan.get_text().startswith('Stopped'), \
        'an aborted search must not report itself as Done'
    assert history.records[-1].get('stopped') is True


@display
def test_minimum_column_widths_on_open(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    from config.config_layout import RESULTS_MIN_WIDTHS
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    off = Gtk.OffscreenWindow()
    off.set_default_size(1100, 600)
    off.add(page)
    off.show_all()
    end = time.time() + 0.8
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    for col in page.view.get_columns():
        minimum = RESULTS_MIN_WIDTHS[col.get_title()]
        assert col.get_min_width() >= minimum, col.get_title()
        assert col.get_width() >= minimum, \
            f"{col.get_title()} rendered {col.get_width()}px, " \
            f"below the {minimum}px floor (readability rule r025)"


@display
def test_modified_sorts_numeric_on_epoch(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    page.store.append([None, 'old.txt', '/old', '1 B', 'Plain Text',
                       '2020-01-01', '/home', 1577836800.0])
    page.store.append([None, 'new.txt', '/new', '1 B', 'Plain Text',
                       '2026-09-25', '/home', 1789000000.0])
    page.store.append([None, 'nodate.txt', '/nd', '1 B', 'Plain Text',
                       '—', '/home', 0.0])
    col = next(c for c in page.view.get_columns()
               if c.get_title() == 'Modified')
    col.clicked()                      # ascending: oldest (epoch 0) first
    assert page.store[0][1] == 'nodate.txt'
    col.clicked()                      # descending: newest first
    assert page.store[0][1] == 'new.txt'


@display
def test_scope_selection_surveys_repopulate(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from pages.page_search import SearchPage
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    chips = [p for p in page.mount_buttons if p != '__all__']
    if not chips:
        pytest.skip('no searchable mounts on this host')
    page.mount_buttons[chips[0]].set_active(True)
    page.populate_scope_chips()        # what a mount event / refresh does
    assert page.mount_buttons[chips[0]].get_active(), \
        'scope choice must survive a scope-chip rebuild'
    assert not page.mount_buttons['__all__'].get_active()
    assert page.selected_roots() == [chips[0]]


@display
def test_preview_property_values_sit_beside_keys(tmp_path):
    gi = pytest.importorskip('gi')
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk
    import ui.dashboard_window  # noqa: F401
    from modules.manager_mounts import MountManager
    from modules.manager_history import HistoryManager
    from modules.manager_theme_applicator import ThemeApplicator
    from utils.manager_theme import ThemeManager
    from config.config_themes import get_theme
    from pages.page_search import SearchPage
    ThemeApplicator().apply_theme(get_theme('default'))
    ThemeManager().load_css('resources/css/style.css')
    page = SearchPage(MountManager(),
                      HistoryManager(config_dir=str(tmp_path / 'cfg')))
    off = Gtk.OffscreenWindow()
    off.set_default_size(1200, 800)
    off.add(page)
    off.show_all()
    end = time.time() + 0.8
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    target = tmp_path / 'LinShot_1.png'
    target.write_bytes(b'\x89PNG\r\n\x1a\n')
    page.store.append([None, 'LinShot_1.png', str(target), '9 B', 'Image',
                       '2026-09-25', str(tmp_path), 1789000000.0])
    page.view.get_selection().select_path(Gtk.TreePath.new_first())
    end = time.time() + 0.4
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    pane_w = page.preview_revealer.get_child().get_allocation().width
    for r in range(5):
        k = page.pv_props.get_child_at(0, r)
        v = page.pv_props.get_child_at(1, r)
        gap = v.get_allocation().x - (k.get_allocation().x
                                      + k.get_allocation().width)
        assert 0 <= gap <= 14, \
            f"row {r}: value drifted {gap}px from its key"
        assert v.get_allocation().x < pane_w * 0.6, \
            f"row {r}: value packed against the pane's right edge"
