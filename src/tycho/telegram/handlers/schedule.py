"""Schedule status and trigger handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from tycho.db import get_schedule_runs, get_session
from tycho.telegram.db_async import run_sync
from tycho.telegram.formatters import format_schedule_status
from tycho.telegram.keyboards import schedule_keyboard


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /schedule command or sched callback."""
    engine = context.bot_data["engine"]
    config = context.bot_data["config"]

    session = await run_sync(get_session, engine)
    try:
        runs = await run_sync(get_schedule_runs, session, limit=5)
    finally:
        await run_sync(session.close)

    # Get next run time from scheduler if available
    next_run = None
    scheduler = context.bot_data.get("scheduler")
    if scheduler:
        from tycho.scheduler.scheduler import get_next_run_time
        next_run = get_next_run_time(scheduler)

    text = format_schedule_status(config, runs, next_run)
    keyboard = schedule_keyboard()

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def schedule_trigger_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle sched_trigger — trigger immediate collection."""
    query = update.callback_query
    await query.answer("Triggering collection...")
    await query.edit_message_text("Running collection... please wait.")

    engine = context.bot_data["engine"]
    config = context.bot_data["config"]

    try:
        from tycho.scheduler.scheduler import trigger_now
        await run_sync(trigger_now, config, engine)
    except Exception as e:
        await query.edit_message_text(f"Collection failed: {e}")
        return

    # Show updated schedule status
    session = await run_sync(get_session, engine)
    try:
        runs = await run_sync(get_schedule_runs, session, limit=5)
    finally:
        await run_sync(session.close)

    next_run = None
    scheduler = context.bot_data.get("scheduler")
    if scheduler:
        from tycho.scheduler.scheduler import get_next_run_time
        next_run = get_next_run_time(scheduler)

    text = format_schedule_status(config, runs, next_run)
    text = "\u2705 Collection complete!\n\n" + text
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=schedule_keyboard())
