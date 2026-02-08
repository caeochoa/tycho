"""Job list with pagination and filters."""

import math

from telegram import Update
from telegram.ext import ContextTypes

from tycho.db import get_jobs_paginated, get_session
from tycho.telegram.db_async import run_sync
from tycho.telegram.formatters import format_job_line
from tycho.telegram.keyboards import (
    job_list_keyboard,
    score_filter_keyboard,
    status_filter_keyboard,
)


async def _show_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     page: int, status_filter: str, score_filter: str) -> None:
    """Shared logic for displaying paginated job list."""
    engine = context.bot_data["engine"]
    config = context.bot_data["config"]
    page_size = config.telegram.page_size

    offset = (page - 1) * page_size
    min_score = float(score_filter) if score_filter else None

    session = await run_sync(get_session, engine)
    try:
        jobs, total = await run_sync(
            get_jobs_paginated, session,
            status=status_filter or None,
            min_score=min_score,
            offset=offset,
            limit=page_size,
        )
    finally:
        await run_sync(session.close)

    total_pages = max(1, math.ceil(total / page_size))

    if not jobs:
        text = "No jobs found."
    else:
        lines = [f"<b>Jobs</b> (page {page}/{total_pages}, {total} total)\n"]
        for i, job in enumerate(jobs, start=1):
            lines.append(format_job_line(job, i))
        text = "\n".join(lines)

    keyboard = job_list_keyboard(jobs, page, total, page_size, status_filter, score_filter)

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /jobs command."""
    await _show_jobs(update, context, page=1, status_filter="", score_filter="")


async def jobs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle jobs:{page}:{status}:{min_score} callback."""
    query = update.callback_query
    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    status_filter = parts[2] if len(parts) > 2 else ""
    score_filter = parts[3] if len(parts) > 3 else ""
    await _show_jobs(update, context, page, status_filter, score_filter)


async def filter_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show status filter menu."""
    query = update.callback_query
    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    score_filter = parts[2] if len(parts) > 2 else ""
    await query.answer()
    await query.edit_message_text(
        "Filter by status:",
        reply_markup=status_filter_keyboard(page, score_filter),
    )


async def filter_score_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show score filter menu."""
    query = update.callback_query
    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1] else 1
    status_filter = parts[2] if len(parts) > 2 else ""
    await query.answer()
    await query.edit_message_text(
        "Filter by minimum score:",
        reply_markup=score_filter_keyboard(page, status_filter),
    )
