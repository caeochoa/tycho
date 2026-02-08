"""Inline keyboard builders for Telegram bot."""

import math

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001f4bc Browse Jobs", callback_data="jobs:1::"),
            InlineKeyboardButton("\U0001f4c5 Schedule", callback_data="sched"),
        ],
        [InlineKeyboardButton("\u2753 Help", callback_data="help")],
    ])


def job_list_keyboard(
    jobs, page: int, total: int, page_size: int, status_filter: str, score_filter: str
) -> InlineKeyboardMarkup:
    """Build keyboard for paginated job list."""
    total_pages = max(1, math.ceil(total / page_size))
    rows = []

    # Job number buttons (tap to view detail)
    num_buttons = []
    for i, job in enumerate(jobs, start=1):
        job8 = job.id[:8]
        num_buttons.append(
            InlineKeyboardButton(str(i), callback_data=f"detail:{job8}:{page}")
        )
    if num_buttons:
        rows.append(num_buttons)

    # Filter buttons
    status_label = f"Status: {status_filter}" if status_filter else "Status: All"
    score_label = f"Score: \u2265{score_filter}" if score_filter else "Score: All"
    rows.append([
        InlineKeyboardButton(
            f"\U0001f4ca {status_label}",
            callback_data=f"filter_status:{page}:{score_filter}",
        ),
        InlineKeyboardButton(
            f"\U0001f3af {score_label}",
            callback_data=f"filter_score:{page}:{status_filter}",
        ),
    ])

    # Pagination
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(
            "\u25c0 Prev", callback_data=f"jobs:{page - 1}:{status_filter}:{score_filter}"
        ))
    nav.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(
            "Next \u25b6", callback_data=f"jobs:{page + 1}:{status_filter}:{score_filter}"
        ))
    rows.append(nav)

    rows.append([InlineKeyboardButton("\U0001f3e0 Menu", callback_data="menu")])

    return InlineKeyboardMarkup(rows)


def status_filter_keyboard(page: int, score_filter: str) -> InlineKeyboardMarkup:
    """Filter menu for job status."""
    statuses = ["", "new", "reviewed", "interested", "applied", "rejected", "archived"]
    labels = ["All", "New", "Reviewed", "Interested", "Applied", "Rejected", "Archived"]
    rows = []
    row = []
    for status, label in zip(statuses, labels):
        row.append(InlineKeyboardButton(
            label, callback_data=f"jobs:1:{status}:{score_filter}"
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("\u25c0 Back", callback_data=f"jobs:{page}::{score_filter}")])
    return InlineKeyboardMarkup(rows)


def score_filter_keyboard(page: int, status_filter: str) -> InlineKeyboardMarkup:
    """Filter menu for minimum score."""
    thresholds = ["", "0.3", "0.5", "0.75"]
    labels = ["All", "\u2265 0.30", "\u2265 0.50", "\u2265 0.75"]
    rows = []
    row = []
    for val, label in zip(thresholds, labels):
        row.append(InlineKeyboardButton(
            label, callback_data=f"jobs:1:{status_filter}:{val}"
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("\u25c0 Back", callback_data=f"jobs:{page}:{status_filter}:")])
    return InlineKeyboardMarkup(rows)


def job_detail_keyboard(job8: str, page: int, url: str | None = None) -> InlineKeyboardMarkup:
    """Buttons for a job detail view."""
    rows = [
        [
            InlineKeyboardButton("\U0001f504 Status", callback_data=f"chstatus:{job8}:{page}"),
            InlineKeyboardButton("\U0001f4c4 Generate CV", callback_data=f"gen:{job8}:{page}"),
        ],
    ]
    if url:
        rows.append([InlineKeyboardButton("\U0001f517 Open URL", url=url)])
    rows.append([InlineKeyboardButton("\u25c0 Back", callback_data=f"jobs:{page}::")])
    return InlineKeyboardMarkup(rows)


def status_change_keyboard(job8: str, page: int) -> InlineKeyboardMarkup:
    """Status selection buttons."""
    statuses = ["new", "reviewed", "interested", "applied", "rejected", "archived"]
    rows = []
    row = []
    for s in statuses:
        row.append(InlineKeyboardButton(
            s.capitalize(), callback_data=f"setstatus:{job8}:{s}:{page}"
        ))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("\u25c0 Back", callback_data=f"detail:{job8}:{page}")])
    return InlineKeyboardMarkup(rows)


def generate_options_keyboard(job8: str, page: int, lang: str, fmt: str, cl: bool) -> InlineKeyboardMarkup:
    """CV generation options with toggles."""
    cl_label = "Yes" if cl else "No"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Language: {lang.upper()}", callback_data=f"gen_opt:{job8}:lang"),
            InlineKeyboardButton(f"Format: {fmt.upper()}", callback_data=f"gen_opt:{job8}:fmt"),
        ],
        [
            InlineKeyboardButton(f"Cover Letter: {cl_label}", callback_data=f"gen_opt:{job8}:cl"),
        ],
        [
            InlineKeyboardButton("\u2705 Generate", callback_data=f"gen_exec:{job8}:{lang}:{fmt}:{'1' if cl else '0'}"),
            InlineKeyboardButton("\u25c0 Back", callback_data=f"detail:{job8}:{page}"),
        ],
    ])


def schedule_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\u25b6 Trigger Now", callback_data="sched_trigger"),
            InlineKeyboardButton("\U0001f504 Refresh", callback_data="sched"),
        ],
        [InlineKeyboardButton("\U0001f3e0 Menu", callback_data="menu")],
    ])
