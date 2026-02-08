"""Access control for Telegram bot."""

from telegram import Update
from telegram.ext import filters


def build_user_filter(allowed_users: list[int]) -> filters.BaseFilter:
    """Build a filter that restricts access to allowed users.

    If allowed_users is empty, allow all users (private bot).
    """
    if not allowed_users:
        return filters.ALL
    return filters.User(user_id=allowed_users)


async def unauthorized_handler(update: Update, context) -> None:
    """Reply to unauthorized users."""
    if update.effective_message:
        await update.effective_message.reply_text("Access restricted.")
