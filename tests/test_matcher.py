"""Unit tests for query matchers (pure functions)."""

from modules.manager_search import make_matcher
from config.config_search import MODE_SUBSTRING, MODE_WILDCARD, MODE_REGEX


def test_substring_case_insensitive():
    match = make_matcher('REPORT', MODE_SUBSTRING, case_sensitive=False)
    assert match('annual-report-2025.pdf')
    assert match('Report_Final.odt')
    assert not match('summary.docx')


def test_substring_case_sensitive():
    match = make_matcher('Report', MODE_SUBSTRING, case_sensitive=True)
    assert match('Report_Final.odt')
    assert not match('annual-report-2025.pdf')


def test_wildcard():
    match = make_matcher('report*.odt', MODE_WILDCARD, case_sensitive=False)
    assert match('report-2026.odt')
    assert match('REPORT.odt')
    assert not match('report.docx')
    assert not match('q3-financial-report.odt')   # fnmatch is full-match (find -name)
    anywhere = make_matcher('*report*.odt', MODE_WILDCARD)
    assert anywhere('q3-financial-report.odt')
    assert not anywhere('file.txt')


def test_regex():
    match = make_matcher(r'^q\d+-.*\.odt$', MODE_REGEX, case_sensitive=False)
    assert match('q3-financial-report.odt')
    assert not match('annual-report-2025.pdf')


def test_invalid_regex_matches_nothing():
    match = make_matcher('([unclosed', MODE_REGEX)
    assert match('anything.txt') is False


def test_empty_query_returns_none():
    assert make_matcher('', MODE_SUBSTRING) is None
