"""Start, help, and main menu handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from tycho.telegram.keyboards import main_menu_keyboard

WELCOME_TEXT = (
    "<b>Welcome to Tycho!</b>\n\n"
    "Browse jobs, update statuses, generate CVs, and trigger collection \u2014 "
    "all from Telegram.\n\n"
    "Commands:\n"
    "/jobs \u2014 Browse jobs\n"
    "/schedule \u2014 Scheduler status\n"
    "/help \u2014 Show this help"
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )
    else:
        # Called as /help command
        await update.message.reply_text(
            WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
        )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        WELCOME_TEXT, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )
