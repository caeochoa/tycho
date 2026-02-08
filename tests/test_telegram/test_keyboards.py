"""Tests for inline keyboard builders."""

from tycho.models import Job, JobStatus
from tycho.telegram.keyboards import (
    generate_options_keyboard,
    job_detail_keyboard,
    job_list_keyboard,
    main_menu_keyboard,
    schedule_keyboard,
    score_filter_keyboard,
    status_change_keyboard,
    status_filter_keyboard,
)


def _flatten_callbacks(keyboard):
    """Extract all callback_data values from an InlineKeyboardMarkup."""
    results = []
    for row in keyboard.inline_keyboard:
        for btn in row:
            if btn.callback_data:
                results.append(btn.callback_data)
    return results


def _flatten_labels(keyboard):
    """Extract all button text from an InlineKeyboardMarkup."""
    results = []
    for row in keyboard.inline_keyboard:
        for btn in row:
            results.append(btn.text)
    return results


class TestMainMenuKeyboard:
    def test_has_jobs_and_schedule(self):
        kb = main_menu_keyboard()
        callbacks = _flatten_callbacks(kb)
        assert "jobs:1::" in callbacks
        assert "sched" in callbacks
        assert "help" in callbacks


class TestJobListKeyboard:
    def test_number_buttons_match_jobs(self):
        jobs = [
            Job(id="aaa11111", source="t", title="J1", company="C1"),
            Job(id="bbb22222", source="t", title="J2", company="C2"),
        ]
        kb = job_list_keyboard(jobs, page=1, total=2, page_size=5, status_filter="", score_filter="")
        callbacks = _flatten_callbacks(kb)
        assert "detail:aaa11111:1" in callbacks
        assert "detail:bbb22222:1" in callbacks

    def test_pagination_first_page(self):
        jobs = [Job(id=f"j{i:07d}0", source="t", title=f"J{i}", company="C") for i in range(5)]
        kb = job_list_keyboard(jobs, page=1, total=15, page_size=5, status_filter="", score_filter="")
        callbacks = _flatten_callbacks(kb)
        assert any("jobs:2::" in c for c in callbacks)  # Next
        assert not any("jobs:0::" in c for c in callbacks)  # No Prev on page 1

    def test_pagination_middle_page(self):
        jobs = [Job(id=f"j{i:07d}0", source="t", title=f"J{i}", company="C") for i in range(5)]
        kb = job_list_keyboard(jobs, page=2, total=15, page_size=5, status_filter="", score_filter="")
        callbacks = _flatten_callbacks(kb)
        assert any("jobs:1::" in c for c in callbacks)  # Prev
        assert any("jobs:3::" in c for c in callbacks)  # Next

    def test_pagination_last_page(self):
        jobs = [Job(id="j0000001", source="t", title="J1", company="C")]
        kb = job_list_keyboard(jobs, page=3, total=11, page_size=5, status_filter="", score_filter="")
        callbacks = _flatten_callbacks(kb)
        assert any("jobs:2::" in c for c in callbacks)  # Prev
        assert not any("jobs:4::" in c for c in callbacks)  # No Next on last page

    def test_filter_buttons_present(self):
        kb = job_list_keyboard([], page=1, total=0, page_size=5, status_filter="new", score_filter="0.5")
        callbacks = _flatten_callbacks(kb)
        assert any("filter_status:" in c for c in callbacks)
        assert any("filter_score:" in c for c in callbacks)

    def test_menu_button(self):
        kb = job_list_keyboard([], page=1, total=0, page_size=5, status_filter="", score_filter="")
        callbacks = _flatten_callbacks(kb)
        assert "menu" in callbacks

    def test_empty_jobs(self):
        kb = job_list_keyboard([], page=1, total=0, page_size=5, status_filter="", score_filter="")
        # Should not crash, first row has no number buttons
        assert len(kb.inline_keyboard) >= 2  # filters + pagination + menu


class TestStatusFilterKeyboard:
    def test_includes_all_statuses(self):
        kb = status_filter_keyboard(page=1, score_filter="")
        labels = _flatten_labels(kb)
        for status in ["All", "New", "Reviewed", "Interested", "Applied", "Rejected", "Archived"]:
            assert status in labels

    def test_back_button(self):
        kb = status_filter_keyboard(page=2, score_filter="0.5")
        callbacks = _flatten_callbacks(kb)
        assert any("jobs:2:" in c for c in callbacks)


class TestScoreFilterKeyboard:
    def test_includes_thresholds(self):
        kb = score_filter_keyboard(page=1, status_filter="")
        labels = _flatten_labels(kb)
        assert "All" in labels
        assert any("0.30" in l for l in labels)
        assert any("0.50" in l for l in labels)
        assert any("0.75" in l for l in labels)

    def test_back_button(self):
        kb = score_filter_keyboard(page=3, status_filter="interested")
        callbacks = _flatten_callbacks(kb)
        assert any("jobs:3:interested:" in c for c in callbacks)


class TestJobDetailKeyboard:
    def test_has_status_and_generate(self):
        kb = job_detail_keyboard("abc12345", page=2)
        callbacks = _flatten_callbacks(kb)
        assert "chstatus:abc12345:2" in callbacks
        assert "gen:abc12345:2" in callbacks

    def test_url_button_when_present(self):
        kb = job_detail_keyboard("abc12345", page=1, url="https://example.com")
        has_url_btn = any(
            btn.url == "https://example.com"
            for row in kb.inline_keyboard
            for btn in row
        )
        assert has_url_btn

    def test_no_url_button_when_absent(self):
        kb = job_detail_keyboard("abc12345", page=1, url=None)
        url_buttons = [
            btn for row in kb.inline_keyboard for btn in row if btn.url
        ]
        assert len(url_buttons) == 0

    def test_back_button(self):
        kb = job_detail_keyboard("abc12345", page=3)
        callbacks = _flatten_callbacks(kb)
        assert "jobs:3::" in callbacks


class TestStatusChangeKeyboard:
    def test_all_statuses_present(self):
        kb = status_change_keyboard("abc12345", page=1)
        callbacks = _flatten_callbacks(kb)
        for status in ["new", "reviewed", "interested", "applied", "rejected", "archived"]:
            assert any(f"setstatus:abc12345:{status}:1" == c for c in callbacks)

    def test_back_button(self):
        kb = status_change_keyboard("abc12345", page=2)
        callbacks = _flatten_callbacks(kb)
        assert "detail:abc12345:2" in callbacks


class TestGenerateOptionsKeyboard:
    def test_shows_current_options(self):
        kb = generate_options_keyboard("abc12345", page=1, lang="en", fmt="pdf", cl=False)
        labels = _flatten_labels(kb)
        assert any("EN" in l for l in labels)
        assert any("PDF" in l for l in labels)
        assert any("No" in l for l in labels)

    def test_cover_letter_yes(self):
        kb = generate_options_keyboard("abc12345", page=1, lang="es", fmt="docx", cl=True)
        labels = _flatten_labels(kb)
        assert any("ES" in l for l in labels)
        assert any("DOCX" in l for l in labels)
        assert any("Yes" in l for l in labels)

    def test_generate_callback(self):
        kb = generate_options_keyboard("abc12345", page=1, lang="en", fmt="pdf", cl=False)
        callbacks = _flatten_callbacks(kb)
        assert "gen_exec:abc12345:en:pdf:0" in callbacks

    def test_back_button(self):
        kb = generate_options_keyboard("abc12345", page=2, lang="en", fmt="pdf", cl=False)
        callbacks = _flatten_callbacks(kb)
        assert "detail:abc12345:2" in callbacks


class TestScheduleKeyboard:
    def test_has_trigger_and_refresh(self):
        kb = schedule_keyboard()
        callbacks = _flatten_callbacks(kb)
        assert "sched_trigger" in callbacks
        assert "sched" in callbacks
        assert "menu" in callbacks
