"""Job detail view and status update handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from tycho.db import get_job_by_prefix, get_session, update_job_status
from tycho.telegram.db_async import run_sync
from tycho.telegram.formatters import format_job_detail
from tycho.telegram.keyboards import job_detail_keyboard, status_change_keyboard


async def detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle detail:{job8}:{page} callback."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2] else 1

    engine = context.bot_data["engine"]
    config = context.bot_data["config"]

    session = await run_sync(get_session, engine)
    try:
        job, error = await run_sync(get_job_by_prefix, session, job8)
    finally:
        await run_sync(session.close)

    await query.answer()

    if error or not job:
        await query.edit_message_text(error or "Job not found.")
        return

    text = format_job_detail(job, config.scoring.thresholds)
    keyboard = job_detail_keyboard(job8, page, url=job.url or None)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def status_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle chstatus:{job8}:{page} — show status selection."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2] else 1

    await query.answer()
    await query.edit_message_text(
        "Change status:", reply_markup=status_change_keyboard(job8, page)
    )


async def set_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle setstatus:{job8}:{status}:{page} — execute status change."""
    query = update.callback_query
    parts = query.data.split(":")
    job8 = parts[1]
    new_status = parts[2]
    page = int(parts[3]) if len(parts) > 3 and parts[3] else 1

    engine = context.bot_data["engine"]

    session = await run_sync(get_session, engine)
    try:
        job, error = await run_sync(get_job_by_prefix, session, job8)
        if job:
            await run_sync(update_job_status, session, job.id, new_status)
            await run_sync(session.commit)
    finally:
        await run_sync(session.close)

    if error or not job:
        await query.answer(error or "Job not found.")
        return

    await query.answer(f"Status \u2192 {new_status}")

    # Reload and show updated detail
    session = await run_sync(get_session, engine)
    try:
        job, _ = await run_sync(get_job_by_prefix, session, job8)
    finally:
        await run_sync(session.close)

    if job:
        config = context.bot_data["config"]
        text = format_job_detail(job, config.scoring.thresholds)
        keyboard = job_detail_keyboard(job8, page, url=job.url or None)
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
