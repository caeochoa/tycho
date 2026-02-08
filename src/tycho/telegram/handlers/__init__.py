"""Register all Telegram bot handlers."""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from tycho.telegram.middleware import build_user_filter, unauthorized_handler


def register_handlers(app: Application, allowed_users: list[int]) -> None:
    """Add all command and callback handlers to the Application."""
    from tycho.telegram.handlers.detail import detail_callback, set_status_callback, status_menu_callback
    from tycho.telegram.handlers.generate import gen_exec_callback, gen_options_callback, gen_toggle_callback
    from tycho.telegram.handlers.jobs import filter_score_callback, filter_status_callback, jobs_callback, jobs_command
    from tycho.telegram.handlers.schedule import schedule_callback, schedule_trigger_callback
    from tycho.telegram.handlers.start import help_callback, menu_callback, start_command

    user_filter = build_user_filter(allowed_users)

    def protected(handler):
        """Wrapper to restrict callback handlers to allowed users."""
        if not allowed_users:
            return handler

        async def wrapped(update, context):
            if update.effective_user.id not in allowed_users:
                if update.callback_query:
                    await update.callback_query.answer("Access restricted.", show_alert=True)
                return
            return await handler(update, context)

        return wrapped

    # Commands
    app.add_handler(CommandHandler("start", start_command, filters=user_filter))
    app.add_handler(CommandHandler("jobs", jobs_command, filters=user_filter))
    app.add_handler(CommandHandler("schedule", schedule_callback, filters=user_filter))
    app.add_handler(CommandHandler("help", help_callback, filters=user_filter))

    # Callback queries — order matters, more specific patterns first
    callbacks = [
        ("^menu$", menu_callback),
        ("^help$", help_callback),
        ("^noop$", lambda u, c: u.callback_query.answer()),
        ("^jobs:", jobs_callback),
        ("^filter_status:", filter_status_callback),
        ("^filter_score:", filter_score_callback),
        ("^detail:", detail_callback),
        ("^chstatus:", status_menu_callback),
        ("^setstatus:", set_status_callback),
        ("^gen_exec:", gen_exec_callback),
        ("^gen_opt:", gen_toggle_callback),
        ("^gen:", gen_options_callback),
        ("^sched_trigger$", schedule_trigger_callback),
        ("^sched$", schedule_callback),
    ]
    for pattern, handler in callbacks:
        app.add_handler(CallbackQueryHandler(protected(handler), pattern=pattern))

    # Catch-all for unauthorized users (must be last)
    if allowed_users:
        app.add_handler(MessageHandler(~user_filter, unauthorized_handler))
